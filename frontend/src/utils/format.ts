export function maskStudentNo(value: string): string {
  if (value.length <= 4) return '*'.repeat(value.length)
  return `${value.slice(0, 2)}${'*'.repeat(value.length - 4)}${value.slice(-2)}`
}

export function competitionLabel(status: string): string {
  return ({ NORMAL: '正常完赛', DNS: '未出发', DNF: '未完成', DQ: '取消资格', NM: '无有效成绩' } as Record<string, string>)[status] || status
}

