import { describe, expect, it } from 'vitest'
import { competitionLabel, maskStudentNo } from '../../../frontend/src/utils/format'

describe('result display utilities', () => {
  it('masks student numbers on public pages', () => expect(maskStudentNo('26001001')).toBe('26****01'))
  it('uses standard competition labels', () => expect(competitionLabel('DQ')).toBe('取消资格'))
})

