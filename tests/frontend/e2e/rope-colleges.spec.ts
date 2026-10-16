import { expect, test } from '@playwright/test'
import path from 'node:path'

test('rope college selector includes all eight colleges after synchronizing missing registrations', async ({ page, request }) => {
  const apiBase = 'http://127.0.0.1:8001/api/v1'
  const colleges = ['信息工程学院', '机电工程学院', '外国语学院', '食品工程学院', '艺术设计学院', '建筑工程学院', '人文学院', '经济管理学院']
  const suffix = String(Date.now())
  const login = await request.post(`${apiBase}/auth/admin-login`, { data: { username: 'admin0001', password: 'Admin123456!' } })
  const auth = await login.json()
  const headers = { Authorization: `Bearer ${auth.access_token}` }
  const created = await request.post(`${apiBase}/sports-teacher/meets`, { headers, data: {
    name: `八学院跳绳验收${suffix}`, edition: suffix, start_date: '2101-10-20', end_date: '2101-10-21',
  } })
  expect(created.ok()).toBeTruthy()
  const meet = await created.json()
  for (const college of colleges.slice(0, 5)) {
    expect((await request.post(`${apiBase}/sports-teacher/college-teams`, { headers, data: { meet_id: meet.id, college } })).ok()).toBeTruthy()
  }
  expect((await request.post(`${apiBase}/sports-teacher/rope/initialize`, { headers, data: { meet_id: meet.id } })).ok()).toBeTruthy()
  for (const college of colleges.slice(5)) {
    expect((await request.post(`${apiBase}/sports-teacher/college-teams`, { headers, data: { meet_id: meet.id, college } })).ok()).toBeTruthy()
  }
  const synced = await request.post(`${apiBase}/sports-teacher/rope/initialize`, { headers, data: { meet_id: meet.id } })
  expect(synced.ok()).toBeTruthy()
  expect((await synced.json()).college_count).toBe(8)
  const status = await (await request.get(`${apiBase}/sports-teacher/rope/status?meet_id=${meet.id}`, { headers })).json()
  expect(status.events).toHaveLength(3)
  for (const event of status.events) expect(event.teams).toHaveLength(8)
  await page.goto('/login')
  await page.getByRole('button', { name: '管理人员', exact: true }).click()
  await page.getByPlaceholder('请输入用户名').fill('admin0001')
  await page.getByPlaceholder('请输入密码').fill('Admin123456!')
  await page.getByRole('button', { name: '进入系统' }).click()
  await expect(page).toHaveURL(/\/app$/)
  await page.getByRole('button', { name: '跳绳赛制', exact: true }).click()
  await expect(page.getByText('已关联 8 个学院', { exact: true })).toBeVisible()
  await page.locator('.el-select').filter({ hasText: '全部学院' }).click()
  const options = page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
  await expect(options).toHaveCount(8)
  for (const college of colleges) await expect(options.filter({ hasText: `${college} ·` })).toHaveCount(1)
  await page.screenshot({ path: path.join(process.env.SPORTS_E2E_RUNTIME_DIR || path.resolve(__dirname, '../../.runtime/e2e'), 'rope-eight-colleges.png'), fullPage: true })
})
