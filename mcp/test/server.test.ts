import { describe, it, expect } from 'vitest';
import { generateDsl } from '../src/server';

describe('generateDsl', () => {
  it('produces valid WOD header and block', () => {
    const dsl = generateDsl({ mode: 'AMRAP', duration: '12:00', teamSize: 2, focus: ['legs'] });
    expect(dsl).toMatch(/WOD "/);
    expect(dsl).toMatch(/TEAM 2/);
    expect(dsl).toMatch(/BLOCK AMRAP 12:00/);
    expect(dsl).toMatch(/air_squat/);
  });
});

