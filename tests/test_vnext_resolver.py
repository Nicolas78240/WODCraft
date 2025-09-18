#!/usr/bin/env python3
"""
Test suite for WODCraft vNext module resolver functionality
"""

import pytest
import tempfile
from pathlib import Path
from src.wodcraft.core import ModuleRef, InMemoryResolver, FileSystemResolver, ResolvedModule


class TestModuleRef:
    """Test ModuleRef functionality"""
    
    def test_module_ref_creation(self):
        """Test creating ModuleRef instances"""
        ref = ModuleRef("warmup", "full_body_10m", "v1")
        
        assert ref.namespace == "warmup"
        assert ref.name == "full_body_10m"
        assert ref.version == "v1"
        
    def test_module_ref_default_version(self):
        """Test ModuleRef with default version"""
        ref = ModuleRef("skill", "snatch")
        
        assert ref.namespace == "skill"
        assert ref.name == "snatch"
        assert ref.version == "v1"  # Default version
        
    def test_module_ref_full_name(self):
        """Test full_name property"""
        ref = ModuleRef("wod", "triplet", "v2")
        assert ref.full_name == "wod.triplet@v2"
        
        ref_default = ModuleRef("warmup", "basic")
        assert ref_default.full_name == "warmup.basic@v1"


class TestInMemoryResolver:
    """Test InMemoryResolver functionality"""
    
    def test_register_and_resolve(self):
        """Test registering and resolving modules"""
        resolver = InMemoryResolver()
        ref = ModuleRef("test", "module", "v1")
        source = '''
        module test.module v1 {
          warmup "Test" {
            block "Test Block" {
              10 Squats
            }
          }
        }
        '''
        
        resolver.register(ref, source)
        resolved = resolver.resolve(ref)
        
        assert resolved.source == source
        assert resolved.ast is None  # Not parsed by default
        
    def test_resolve_nonexistent_module_raises_error(self):
        """Test that resolving non-existent module raises error"""
        resolver = InMemoryResolver()
        ref = ModuleRef("nonexistent", "module")
        
        with pytest.raises(ValueError, match="Module not found"):
            resolver.resolve(ref)
            
    def test_list_modules(self):
        """Test listing registered modules"""
        resolver = InMemoryResolver()
        
        # Register multiple modules
        refs = [
            ModuleRef("warmup", "basic", "v1"),
            ModuleRef("warmup", "advanced", "v1"),
            ModuleRef("skill", "olympic", "v2")
        ]
        
        for ref in refs:
            resolver.register(ref, f"module {ref.namespace}.{ref.name} {ref.version} {{}}")
            
        # List all modules
        all_modules = resolver.list()
        assert len(all_modules) == 3
        
        # List by namespace
        warmup_modules = resolver.list("warmup")
        assert len(warmup_modules) == 2
        
        skill_modules = resolver.list("skill")
        assert len(skill_modules) == 1
        
    def test_multiple_versions(self):
        """Test handling multiple versions of same module"""
        resolver = InMemoryResolver()
        
        ref_v1 = ModuleRef("test", "versioned", "v1")
        ref_v2 = ModuleRef("test", "versioned", "v2")
        
        source_v1 = "module test.versioned v1 { /* v1 content */ }"
        source_v2 = "module test.versioned v2 { /* v2 content */ }"
        
        resolver.register(ref_v1, source_v1)
        resolver.register(ref_v2, source_v2)
        
        resolved_v1 = resolver.resolve(ref_v1)
        resolved_v2 = resolver.resolve(ref_v2)
        
        assert resolved_v1.source == source_v1
        assert resolved_v2.source == source_v2
        assert resolved_v1.source != resolved_v2.source


class TestFileSystemResolver:
    """Test FileSystemResolver functionality"""
    
    def test_resolve_existing_module(self):
        """Test resolving module from filesystem"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create module directory structure
            warmup_dir = temp_path / "warmup"
            warmup_dir.mkdir()
            
            # Create module file
            module_file = warmup_dir / "test_module.wodcraft"
            module_content = '''
            module warmup.test_module v1 {
              @tag("test")
              warmup "Test Warmup" {
                block "Movement" {
                  10 Air_Squats
                }
              }
            }
            '''
            module_file.write_text(module_content)
            
            # Test resolver
            resolver = FileSystemResolver(temp_path)
            ref = ModuleRef("warmup", "test_module", "v1")
            
            resolved = resolver.resolve(ref)
            
            assert module_content.strip() in resolved.source.strip()
            
    def test_resolve_nonexistent_file_raises_error(self):
        """Test that resolving non-existent file raises error"""
        with tempfile.TemporaryDirectory() as temp_dir:
            resolver = FileSystemResolver(temp_dir)
            ref = ModuleRef("missing", "module")
            
            with pytest.raises(ValueError, match="Module file not found"):
                resolver.resolve(ref)
                
    def test_list_modules_from_filesystem(self):
        """Test listing modules from filesystem"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create multiple module files
            modules = [
                ("warmup", "basic.wodcraft"),
                ("warmup", "advanced.wodcraft"),
                ("skill", "olympic.wodcraft"),
                ("wod", "crossfit.wodcraft")
            ]
            
            for namespace, filename in modules:
                ns_dir = temp_path / namespace
                ns_dir.mkdir(exist_ok=True)
                (ns_dir / filename).write_text(f"module {namespace}.{filename[:-9]} v1 {{}}")
                
            resolver = FileSystemResolver(temp_path)
            
            # List all modules
            all_modules = resolver.list()
            assert len(all_modules) == 4
            
            # List by namespace
            warmup_modules = resolver.list("warmup")
            assert len(warmup_modules) == 2
            
            # Verify module names are correct
            warmup_names = [mod.name for mod in warmup_modules]
            assert "basic" in warmup_names
            assert "advanced" in warmup_names
            
    def test_nested_module_paths(self):
        """Test handling nested module paths"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            nested_dir = temp_path / "warmup" / "mobility"
            nested_dir.mkdir(parents=True)
            
            module_file = nested_dir / "shoulder.wodcraft"
            module_file.write_text("module warmup.mobility.shoulder v1 {}")
            
            resolver = FileSystemResolver(temp_path)
            ref = ModuleRef("warmup", "mobility.shoulder")
            
            resolved = resolver.resolve(ref)
            assert "warmup.mobility.shoulder" in resolved.source


class TestResolvedModule:
    """Test ResolvedModule functionality"""
    
    def test_resolved_module_creation(self):
        """Test creating ResolvedModule instances"""
        source = "module test v1 {}"
        ast = {"type": "MODULE"}
        meta = {"author": "test"}
        
        resolved = ResolvedModule(source, ast, meta)
        
        assert resolved.source == source
        assert resolved.ast == ast
        assert resolved.meta == meta
        
    def test_resolved_module_defaults(self):
        """Test ResolvedModule with default values"""
        source = "module test v1 {}"
        resolved = ResolvedModule(source)
        
        assert resolved.source == source
        assert resolved.ast is None
        assert resolved.meta == {}


class TestResolverIntegration:
    """Integration tests for resolver functionality"""
    
    def test_resolver_with_real_modules(self):
        """Test resolver with actual module files from the project"""
        # Test with the real modules we created
        resolver = FileSystemResolver("modules")
        
        # Test resolving warmup module
        warmup_ref = ModuleRef("warmup", "full_body_10m", "v1")
        
        try:
            resolved = resolver.resolve(warmup_ref)
            assert "warmup.full_body_10m" in resolved.source
            assert "Full Body" in resolved.source
        except ValueError:
            # Module file might not exist in test environment
            pytest.skip("Real module files not available in test environment")
            
    def test_resolver_performance(self):
        """Test resolver performance with many modules"""
        resolver = InMemoryResolver()
        
        # Register many modules
        for i in range(100):
            ref = ModuleRef("perf", f"module_{i}", "v1")
            resolver.register(ref, f"module perf.module_{i} v1 {{}}")
            
        # Test resolution speed
        import time
        start_time = time.time()
        
        for i in range(10):
            ref = ModuleRef("perf", f"module_{i}", "v1")
            resolver.resolve(ref)
            
        end_time = time.time()
        
        # Should resolve quickly (less than 0.1 seconds for 10 resolutions)
        assert (end_time - start_time) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])