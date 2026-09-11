import { describe, expect, it } from 'vitest'
import { competitionLabel, maskStudentNo } from './format'

describe('result display utilities', () => {
  it('masks student numbers on public pages', () => expect(maskStudentNo('2026001001')).toBe('20******01'))
  it('uses standard competition labels', () => expect(competitionLabel('DQ')).toBe('取消资格'))
})

