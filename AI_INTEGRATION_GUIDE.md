# WODCraft Integration Guide for AI Agents

This guide provides AI agents with the proper patterns and best practices for integrating WODCraft into web applications, mobile apps, and desktop software.

## 🎯 Core Integration Patterns

### 1. Parser-First Architecture
Always parse WOD content through WODCraft before processing:

```bash
# Validate WOD syntax first
python3 wodc_merged.py lint workout.wod --catalog box_catalog.json --track RX --gender male

# Then parse to structured JSON
python3 wodc_merged.py parse workout.wod -o structured_wod.json
```

### 2. Track & Gender Resolution
Apply user-specific variants during processing:

```python
# Example integration pattern
def process_wod_for_user(wod_content, user_track, user_gender):
    # 1. Validate syntax
    lint_result = subprocess.run([
        "python3", "wodc_merged.py", "lint", "workout.wod",
        "--catalog", "box_catalog.json",
        "--track", user_track,
        "--gender", user_gender
    ], capture_output=True)
    
    if lint_result.returncode != 0:
        return {"error": "Invalid WOD syntax", "details": lint_result.stderr}
    
    # 2. Parse to JSON
    parse_result = subprocess.run([
        "python3", "wodc_merged.py", "parse", "workout.wod", "-o", "-"
    ], capture_output=True, text=True)
    
    return json.loads(parse_result.stdout)
```

## 🌐 Web Application Integration

### Frontend (JavaScript/TypeScript)
```javascript
// Client-side WOD rendering
class WODRenderer {
  constructor(wodData, userPreferences) {
    this.wod = wodData;
    this.track = userPreferences.track; // RX, INTERMEDIATE, SCALED
    this.gender = userPreferences.gender; // male, female
  }

  renderWorkout() {
    // Use resolved WOD JSON from backend
    return this.wod.program.map(block => {
      switch(block.type) {
        case 'BUYIN':
          return this.renderBuyin(block);
        case 'BLOCK':
          return this.renderBlock(block);
        case 'CASHOUT':
          return this.renderCashout(block);
        default:
          return null;
      }
    });
  }

  renderBlock(block) {
    return {
      type: block.block_type, // AMRAP, EMOM, FT, etc.
      duration: block.duration,
      movements: block.movements.map(mv => ({
        quantity: this.resolveQuantity(mv.quantity),
        movement: mv.movement,
        load: this.resolveLoad(mv.load),
        modifiers: mv.modifiers || []
      }))
    };
  }

  resolveQuantity(qty) {
    // Handle dual values like "21/15" based on gender
    if (typeof qty === 'string' && qty.includes('/')) {
      const [male, female] = qty.split('/');
      return this.gender === 'male' ? male : female;
    }
    return qty;
  }
}
```

### Backend (Node.js/Python/PHP)
```python
# Server-side WOD processing
from flask import Flask, request, jsonify
import subprocess
import tempfile
import json

app = Flask(__name__)

@app.route('/api/wod/process', methods=['POST'])
def process_wod():
    data = request.get_json()
    wod_content = data['wod_content']
    user_track = data.get('track', 'RX')
    user_gender = data.get('gender', 'male')
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.wod', delete=False) as f:
        f.write(wod_content)
        temp_wod_path = f.name
    
    try:
        # Process through WODCraft
        result = subprocess.run([
            'python3', 'wodc_merged.py', 'parse', temp_wod_path,
            '--resolve', '--catalog', 'box_catalog.json',
            '--track', user_track, '--gender', user_gender,
            '-o', '-'
        ], capture_output=True, text=True, check=True)
        
        wod_json = json.loads(result.stdout)
        
        # Generate timeline for timer
        timeline_result = subprocess.run([
            'python3', 'wodc_merged.py', 'run', temp_wod_path,
            '--format', 'json'
        ], capture_output=True, text=True, check=True)
        
        timeline = json.loads(timeline_result.stdout)
        
        return jsonify({
            'wod': wod_json,
            'timeline': timeline,
            'status': 'success'
        })
        
    except subprocess.CalledProcessError as e:
        return jsonify({
            'error': 'WOD processing failed',
            'details': e.stderr,
            'status': 'error'
        }), 400
    finally:
        os.unlink(temp_wod_path)
```

## 📱 Mobile Application Integration

### React Native / Flutter Pattern
```javascript
// WOD Service for mobile apps
class WODService {
  constructor(apiBaseUrl) {
    this.apiUrl = apiBaseUrl;
  }

  async processWOD(wodContent, userProfile) {
    const response = await fetch(`${this.apiUrl}/api/wod/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        wod_content: wodContent,
        track: userProfile.track,
        gender: userProfile.gender,
        catalog: userProfile.gym_catalog || 'default'
      })
    });

    if (!response.ok) {
      throw new Error('Failed to process WOD');
    }

    return await response.json();
  }

  // Generate workout timer from timeline
  createTimer(timeline) {
    return {
      events: timeline.events,
      totalDuration: timeline.total_duration,
      segments: timeline.segments.map(seg => ({
        name: seg.name,
        duration: seg.duration,
        movements: seg.movements,
        startTime: seg.start_time
      }))
    };
  }
}

// Usage in component
const WorkoutScreen = () => {
  const [wod, setWOD] = useState(null);
  const [timer, setTimer] = useState(null);
  
  useEffect(() => {
    const processWorkout = async () => {
      try {
        const result = await wodService.processWOD(wodContent, userProfile);
        setWOD(result.wod);
        setTimer(wodService.createTimer(result.timeline));
      } catch (error) {
        console.error('WOD processing failed:', error);
      }
    };
    
    processWorkout();
  }, [wodContent, userProfile]);

  return (
    <View>
      <WODDisplay wod={wod} />
      <TimerComponent timeline={timer} />
    </View>
  );
};
```

### Native iOS (Swift) / Android (Kotlin)
```swift
// iOS WOD Processing Service
class WODService {
    private let apiURL: String
    
    init(apiURL: String) {
        self.apiURL = apiURL
    }
    
    func processWOD(content: String, track: String, gender: String) async throws -> WODResult {
        let url = URL(string: "\(apiURL)/api/wod/process")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload = [
            "wod_content": content,
            "track": track,
            "gender": gender
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw WODError.processingFailed
        }
        
        return try JSONDecoder().decode(WODResult.self, from: data)
    }
}

// Data models
struct WODResult: Codable {
    let wod: WODStructure
    let timeline: WorkoutTimeline
    let status: String
}

struct WODStructure: Codable {
    let meta: WODMeta
    let program: [WODBlock]
}

struct WorkoutTimeline: Codable {
    let events: [TimerEvent]
    let totalDuration: TimeInterval
    let segments: [TimelineSegment]
}
```

## 🖥️ Desktop Application Integration

### Electron App
```javascript
// Main process - WOD processing
const { spawn } = require('child_process');
const path = require('path');

class WODProcessor {
  constructor(wodcraftPath) {
    this.wodcraftPath = wodcraftPath;
  }

  processWOD(content, options = {}) {
    return new Promise((resolve, reject) => {
      const args = [
        'parse',
        '-', // stdin
        '--resolve',
        '--catalog', options.catalog || 'box_catalog.json',
        '--track', options.track || 'RX',
        '--gender', options.gender || 'male',
        '-o', '-' // stdout
      ];

      const wodcraft = spawn('python3', [this.wodcraftPath, ...args]);
      
      let stdout = '';
      let stderr = '';

      wodcraft.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      wodcraft.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      wodcraft.on('close', (code) => {
        if (code === 0) {
          try {
            resolve(JSON.parse(stdout));
          } catch (e) {
            reject(new Error('Failed to parse WODCraft output'));
          }
        } else {
          reject(new Error(stderr));
        }
      });

      // Send WOD content to stdin
      wodcraft.stdin.write(content);
      wodcraft.stdin.end();
    });
  }
}

// Renderer process - UI integration
const { ipcRenderer } = require('electron');

class WODEditor {
  constructor(elementId) {
    this.editor = document.getElementById(elementId);
    this.setupEventHandlers();
  }

  setupEventHandlers() {
    this.editor.addEventListener('input', this.debounce(() => {
      this.validateWOD();
    }, 500));
  }

  async validateWOD() {
    const content = this.editor.value;
    try {
      const result = await ipcRenderer.invoke('process-wod', {
        content,
        track: this.getCurrentTrack(),
        gender: this.getCurrentGender()
      });
      
      this.displayValidationSuccess(result);
    } catch (error) {
      this.displayValidationError(error.message);
    }
  }

  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }
}
```

## 🔧 Best Practices for AI Agents

### 1. Error Handling Patterns
```python
def safe_wod_processing(wod_content, user_preferences):
    """Robust WOD processing with comprehensive error handling"""
    try:
        # Step 1: Syntax validation
        lint_cmd = [
            "python3", "wodc_merged.py", "lint", "-",
            "--catalog", user_preferences.get("catalog", "box_catalog.json"),
            "--track", user_preferences.get("track", "RX"),
            "--gender", user_preferences.get("gender", "male")
        ]
        
        lint_result = subprocess.run(
            lint_cmd, 
            input=wod_content, 
            text=True, 
            capture_output=True
        )
        
        if lint_result.returncode != 0:
            return {
                "success": False,
                "error": "syntax_error",
                "details": lint_result.stderr,
                "suggestions": extract_error_suggestions(lint_result.stderr)
            }
        
        # Step 2: Parse to JSON
        parse_cmd = [
            "python3", "wodc_merged.py", "parse", "-", 
            "--resolve", "-o", "-"
        ]
        
        parse_result = subprocess.run(
            parse_cmd,
            input=wod_content,
            text=True,
            capture_output=True,
            check=True
        )
        
        wod_json = json.loads(parse_result.stdout)
        
        return {
            "success": True,
            "wod": wod_json,
            "metadata": {
                "track": user_preferences.get("track"),
                "gender": user_preferences.get("gender"),
                "processed_at": datetime.utcnow().isoformat()
            }
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": "processing_error",
            "details": str(e)
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": "json_parse_error",
            "details": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "error": "unexpected_error",
            "details": str(e)
        }
```

### 2. Caching Strategies
```python
import hashlib
import os
import json
from datetime import datetime, timedelta

class WODCache:
    def __init__(self, cache_dir="./wod_cache", ttl_hours=24):
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        os.makedirs(cache_dir, exist_ok=True)
    
    def get_cache_key(self, wod_content, user_preferences):
        """Generate cache key from WOD content and user preferences"""
        cache_data = {
            "content": wod_content,
            "track": user_preferences.get("track", "RX"),
            "gender": user_preferences.get("gender", "male"),
            "catalog": user_preferences.get("catalog", "box_catalog.json")
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def get(self, wod_content, user_preferences):
        """Retrieve cached WOD processing result"""
        cache_key = self.get_cache_key(wod_content, user_preferences)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if not os.path.exists(cache_file):
            return None
        
        # Check if cache is still valid
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if datetime.now() - file_time > self.ttl:
            os.remove(cache_file)
            return None
        
        with open(cache_file, 'r') as f:
            return json.load(f)
    
    def set(self, wod_content, user_preferences, result):
        """Cache WOD processing result"""
        cache_key = self.get_cache_key(wod_content, user_preferences)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2)
```

### 3. Performance Optimization
```python
import asyncio
import concurrent.futures
from typing import List, Dict, Any

class WODBatchProcessor:
    def __init__(self, max_workers=4):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    
    async def process_multiple_wods(self, wod_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process multiple WODs concurrently"""
        loop = asyncio.get_event_loop()
        
        tasks = []
        for request in wod_requests:
            task = loop.run_in_executor(
                self.executor,
                self.process_single_wod,
                request['content'],
                request['preferences']
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "request_id": wod_requests[i].get("id")
                })
            else:
                processed_results.append({
                    **result,
                    "request_id": wod_requests[i].get("id")
                })
        
        return processed_results
    
    def process_single_wod(self, content: str, preferences: Dict[str, str]) -> Dict[str, Any]:
        """Process a single WOD (runs in thread pool)"""
        return safe_wod_processing(content, preferences)
```

## 🚦 Integration Checklist

### ✅ Pre-Integration
- [ ] Ensure Python 3.7+ is available in deployment environment
- [ ] Install WODCraft dependencies (`requirements.txt`)
- [ ] Validate `box_catalog.json` is accessible
- [ ] Test WODCraft CLI commands work in target environment

### ✅ During Integration
- [ ] Implement proper error handling for all WODCraft operations
- [ ] Add input validation before sending to WODCraft
- [ ] Implement caching for processed WODs
- [ ] Add logging for WODCraft processing steps
- [ ] Test with various WOD formats and edge cases

### ✅ Post-Integration
- [ ] Monitor processing performance and memory usage
- [ ] Set up alerts for WODCraft processing failures
- [ ] Implement health checks for WODCraft availability
- [ ] Document custom catalog format if using gym-specific movements
- [ ] Plan for WODCraft version updates and migrations

## 🔍 Common Pitfalls to Avoid

### ❌ Don't Do This
```python
# Bad: Direct string manipulation of WOD content
def modify_wod(wod_content, new_reps):
    return wod_content.replace("21", str(new_reps))  # Dangerous!

# Bad: Ignoring error codes
result = subprocess.run(["python3", "wodc_merged.py", "parse", "file.wod"])
# Proceeding without checking result.returncode
```

### ✅ Do This Instead
```python
# Good: Parse, modify JSON, regenerate
def modify_wod_safely(wod_content, modifications):
    # 1. Parse to JSON
    wod_json = safe_wod_processing(wod_content, user_prefs)
    if not wod_json["success"]:
        return wod_json
    
    # 2. Modify JSON structure
    modified_json = apply_modifications(wod_json["wod"], modifications)
    
    # 3. Validate modified structure
    return validate_modified_wod(modified_json)

# Good: Always check return codes and handle errors
def safe_subprocess_call(cmd_args, input_data=None):
    try:
        result = subprocess.run(
            cmd_args,
            input=input_data,
            text=True,
            capture_output=True,
            check=True,
            timeout=30  # Prevent hanging
        )
        return {"success": True, "output": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": e.stderr, "code": e.returncode}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Processing timeout"}
```

## 📚 Additional Resources

- **WODCraft Specification**: `WODCraft_spec.md`
- **CLI Reference**: `CLAUDE.md` 
- **Movement Catalog Format**: `box_catalog.json`
- **Example WODs**: `*.wod` files in repository root
- **Error Codes Reference**: See linter section in `wodc_merged.py`

---

*This guide is maintained for AI agents working with WODCraft. Always test integrations thoroughly with representative WOD samples.*