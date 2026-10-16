import { expect, test } from '@playwright/test'
import path from 'node:path'

test('rope registration preview, college print sheets and schedule drafts work through the UI', async ({ page, request }) => {
  test.setTimeout(90_000)
  const apiBase = 'http://127.0.0.1:8001/api/v1'
  const suffix = String(Date.now())
  const login = await request.post(`${apiBase}/auth/admin-login`, { data: { username: 'admin0001', password: 'Admin123456!' } })
  const auth = await login.json()
  const headers = { Authorization: `Bearer ${auth.access_token}` }
  const created = await request.post(`${apiBase}/sports-teacher/meets`, { headers, data: {
    name: `跳绳表格验收${suffix}`, edition: suffix, start_date: '2099-10-20', end_date: '2099-10-21', status: 'PREPARING',
  } })
  expect(created.ok()).toBeTruthy()
  const meet = await created.json()
  expect((await request.post(`${apiBase}/sports-teacher/rope/initialize`, { headers, data: { meet_id: meet.id } })).ok()).toBeTruthy()
  await page.goto('/login')
  await page.getByRole('button', { name: '管理人员', exact: true }).click()
  await page.getByPlaceholder('请输入用户名').fill('admin0001')
  await page.getByPlaceholder('请输入密码').fill('Admin123456!')
  await page.getByRole('button', { name: '进入系统' }).click()
  await expect(page).toHaveURL(/\/app$/)
  await page.getByRole('button', { name: '跳绳赛制', exact: true }).click()
  await expect(page.getByRole('heading', { name: '报名表与比赛用表' })).toBeVisible()
  const templateButton = page.getByRole('button', { name: '下载模板', exact: true })
  await expect(templateButton).toBeEnabled()
  const templateDownload = page.waitForEvent('download')
  await templateButton.click()
  const template = await templateDownload
  expect(template.suggestedFilename()).toBe('跳绳比赛报名表模板.xlsx')
  await template.saveAs(path.resolve(__dirname, '../../.runtime/e2e/rope-registration-template.xlsx'))
  const templateBounds = await templateButton.boundingBox()
  const importBounds = await page.getByRole('button', { name: '导入报名表', exact: true }).boundingBox()
  expect(templateBounds!.x).toBeLessThan(importBounds!.x)
  await page.locator('.el-select').nth(2).click()
  await page.locator('.el-select-dropdown__item').filter({ hasText: `跳绳表格验收${suffix}` }).click()
  await expect(page.getByText('集体单摇跳', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: '导入报名表', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '识别学院跳绳报名表' })
  const people = [
    ...Array.from({ length: 11 }, (_, i) => ({ no: `${String(meet.id).padStart(5, '0')}1${String(i).padStart(2, '0')}`, name: `男队员${i + 1}`, gender: '男' })),
    ...Array.from({ length: 11 }, (_, i) => ({ no: `${String(meet.id).padStart(5, '0')}2${String(i).padStart(2, '0')}`, name: `女队员${i + 1}`, gender: '女' })),
  ]
  const turners = [people[10], people[21]]
  const rows = [['学号', '姓名', '性别', '学院', '项目', '角色']]
  for (const [code, members] of [
    ['ROPE_SINGLE', [...people.slice(0, 5), ...people.slice(11, 16)]],
    ['ROPE_SYNC', [...people.slice(0, 5), ...people.slice(11, 16), ...turners]],
    ['ROPE_FIG8', [...people.slice(0, 10), ...people.slice(11, 21), ...turners]],
  ] as const) {
    for (const person of members) rows.push([person.no, person.name, person.gender, '验收学院', code, turners.includes(person) ? '摇绳者' : '跳绳者'])
  }
  await dialog.locator('input[type=file]').setInputFiles({ name: '学院报名.csv', mimeType: 'text/csv', buffer: Buffer.from('\uFEFF' + rows.map(row => row.join(',')).join('\n')) })
  await dialog.getByRole('button', { name: '识别 / 重新预览' }).click()
  await expect(dialog.getByText('识别到 22 人、44 条报名，去重 0 条')).toBeVisible()
  await expect(dialog.getByRole('button', { name: '确认导入', exact: true })).toBeEnabled()
  await page.screenshot({ path: path.resolve(__dirname, '../../.runtime/e2e/rope-import-preview.png'), fullPage: true })
  await dialog.getByRole('button', { name: '确认导入', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await expect(page.getByRole('cell', { name: '验收学院', exact: true })).toBeVisible()
  const tableDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出手写登记表', exact: true }).click()
  const downloaded = await tableDownload
  expect(downloaded.suggestedFilename()).toBe('跳绳_各学院_成绩登记表.xlsx')
  await downloaded.saveAs(path.resolve(__dirname, '../../.runtime/e2e/rope-record-sheets.xlsx'))
  await page.getByRole('button', { name: '随机抽签 / 生成赛程', exact: true }).click()
  const draw = page.getByRole('dialog', { name: '随机抽签并生成赛程' })
  await draw.getByPlaceholder('学校当地时间').fill('2099-10-20 09:00:00')
  await page.keyboard.press('Enter')
  await draw.locator('.el-form-item').filter({ hasText: '比赛场地' }).locator('input').fill('验收体育馆')
  await draw.getByRole('button', { name: '生成抽签与赛程草稿' }).click()
  await expect(draw).not.toBeVisible()
  const scheduleDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出赛程表', exact: true }).click()
  expect((await scheduleDownload).suggestedFilename()).toBe('跳绳_抽签赛程表.xlsx')
  await page.screenshot({ path: path.resolve(__dirname, '../../.runtime/e2e/rope-workspace.png'), fullPage: true })
})
