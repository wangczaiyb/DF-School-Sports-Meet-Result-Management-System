import { expect, test } from '@playwright/test'

test('developer can log in and open the account workspace', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '登录赛事工作台' })).toBeVisible()
  await page.getByPlaceholder('请输入用户名').fill('developer01')
  await page.getByPlaceholder('请输入密码').fill('Dev123456!')
  await page.getByRole('button', { name: '进入系统' }).click()
  await expect(page).toHaveURL(/\/app$/)
  await expect(page.getByRole('heading', { name: '系统概览' })).toBeVisible()
  await page.getByRole('button', { name: '账号管理', exact: true }).click()
  await expect(page.getByRole('heading', { name: '全部账号' })).toBeVisible()
})

test('public results expose only published records and masked student numbers', async ({ page }) => {
  await page.goto('/results')
  await expect(page.getByRole('heading', { name: '赛事成绩中心' })).toBeVisible()
  const meetSelect = page.locator('.public-meet-select')
  if (await meetSelect.isVisible()) {
    await meetSelect.click()
    const option = page.locator('.el-select-dropdown__item').filter({ hasText: '春季校园田径运动会' })
    if (await option.count() > 0) {
      await option.first().click()
    }
  }
  await expect(page.getByText('男子100米').first()).toBeVisible()
  await expect(page.getByText('26****01').first()).toBeVisible()
  await expect(page.getByText('张晨').first()).toBeVisible()
})

test('core CRUD and result workflow persist through UI, API, public polling and student view', async ({ page, request, context }) => {
  test.setTimeout(120_000)
  const suffix = String(Date.now())
  const meetName = `CODEX_TEST_E2E_运动会_${suffix}`
  const eventName = `CODEX_TEST_E2E_男子测试跑_${suffix}`
  const eventCode = `CE${suffix.slice(-8)}`
  const studentNo = suffix.slice(-8)
  const studentName = `CODEX_TEST_E2E_学生_${suffix.slice(-6)}`
  const apiBase = 'http://127.0.0.1:8001/api/v1'

  const formInput = (dialog: ReturnType<typeof page.locator>, label: string) =>
    dialog.locator('.el-form-item').filter({ hasText: label }).locator('input').first()

  // Browser login as sports teacher.
  await page.goto('/login')
  await page.getByRole('button', { name: '管理人员' }).click()
  await page.getByPlaceholder('请输入用户名').fill('admin0001')
  await page.getByPlaceholder('请输入密码').fill('Admin123456!')
  await page.getByRole('button', { name: '进入系统' }).click()
  await expect(page).toHaveURL(/\/app$/)
  const token = await page.evaluate(() => localStorage.getItem('sports_token'))
  expect(token).toBeTruthy()
  const headers = { Authorization: `Bearer ${token}` }

  // Create a meet in the actual UI and verify it remains visible after the API reload.
  await page.getByRole('button', { name: '赛事与项目', exact: true }).click()
  await page.getByRole('button', { name: '新建运动会届次' }).click()
  const meetDialog = page.locator('.el-dialog').filter({ hasText: '新建运动会' })
  await formInput(meetDialog, '运动会名称').fill(meetName)
  await formInput(meetDialog, '年度/届次标识').fill('2038-综合赛')
  await formInput(meetDialog, '开始日期').fill('2038-09-01')
  await page.keyboard.press('Enter')
  await formInput(meetDialog, '结束日期').fill('2038-09-03')
  await page.keyboard.press('Enter')
  await meetDialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText(meetName).first()).toBeVisible()

  const meetsResponse = await request.get(`${apiBase}/sports-teacher/meets`, { headers })
  expect(meetsResponse.ok()).toBeTruthy()
  const meet = (await meetsResponse.json()).find((row: any) => row.name === meetName)
  expect(meet).toBeTruthy()

  // Create an event in the UI using the new meet context.
  await page.getByRole('button', { name: '新建比赛项目' }).click()
  const eventDialog = page.locator('.el-dialog').filter({ hasText: '新建比赛项目' })
  await formInput(eventDialog, '项目编号').fill(eventCode)
  await formInput(eventDialog, '项目名称').fill(eventName)
  await eventDialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText(eventName).first()).toBeVisible()
  const eventsResponse = await request.get(`${apiBase}/sports-teacher/events?meet_id=${meet.id}`, { headers })
  const event = (await eventsResponse.json()).find((row: any) => row.code === eventCode)
  expect(event?.meet_id).toBe(meet.id)

  // Create a student through the repaired UI form (including backend-required major/class fields).
  await page.getByRole('button', { name: '名单录入', exact: true }).click()
  await page.getByRole('tab', { name: '学生资料库' }).click()
  await page.getByRole('button', { name: '新增学生' }).click()
  const studentDialog = page.locator('.el-dialog').filter({ hasText: '新增学生资料' })
  await formInput(studentDialog, '学号').fill(studentNo)
  await formInput(studentDialog, '姓名').fill(studentName)
  await formInput(studentDialog, '学院').fill('CODEX_TEST_E2E_学院')
  await formInput(studentDialog, '专业').fill('CODEX_TEST_E2E_专业')
  await formInput(studentDialog, '班级').fill('CODEX_TEST_E2E_班级')
  await studentDialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText(studentName).first()).toBeVisible()
  const studentsResponse = await request.get(`${apiBase}/sports-teacher/students?keyword=${studentNo}`, { headers })
  const student = (await studentsResponse.json()).items[0]
  expect(student.student_no).toBe(studentNo)

  // Build the participant list, check in, persist heat/lane and create a published schedule.
  const rosterResponse = await request.get(`${apiBase}/sports-teacher/event-registrations?event_id=${event.id}`, { headers })
  const roster = await rosterResponse.json()
  const heat = roster.rounds.find((row: any) => row.stage === 'HEAT')
  const semifinal = roster.rounds.find((row: any) => row.stage === 'SEMIFINAL')
  const addResponse = await request.post(`${apiBase}/sports-teacher/event-registrations/batch`, {
    headers,
    data: { event_id: event.id, round_id: heat.id, participant_ids: [student.id] },
  })
  expect(addResponse.ok()).toBeTruthy()
  const addedRoster = await (await request.get(`${apiBase}/sports-teacher/event-registrations?event_id=${event.id}&round_id=${heat.id}`, { headers })).json()
  const registration = addedRoster.items.find((row: any) => row.participant.id === student.id)
  expect((await request.put(`${apiBase}/sports-teacher/event-registrations/${registration.id}`, {
    headers,
    data: { bib_no: 'CODEX_TEST_BIB', heat: '第1组', lane: '4', status: 'CHECKED_IN' },
  })).ok()).toBeTruthy()
  expect((await request.post(`${apiBase}/sports-teacher/event-registrations/seed`, {
    headers,
    data: { event_id: event.id, round_id: heat.id, lanes_per_heat: 8 },
  })).ok()).toBeTruthy()
  const scheduleResponse = await request.post(`${apiBase}/admin/schedules`, {
    headers,
    data: {
      event_id: event.id,
      round_id: heat.id,
      competition_at: '2038-09-01T09:00:00',
      check_in_at: '2038-09-01T08:30:00',
      venue: 'CODEX_TEST_E2E_体育场',
      status: 'NOT_STARTED',
      published: true,
    },
  })
  expect(scheduleResponse.ok()).toBeTruthy()

  // Enter, submit, referee-review and final-review the result.
  const savedResultResponse = await request.put(`${apiBase}/admin/results`, {
    headers,
    data: { event_id: event.id, round_id: heat.id, registration_id: registration.id, raw_value: 12.34, competition_status: 'NORMAL', notes: 'CODEX_TEST_E2E_公开快照' },
  })
  expect(savedResultResponse.ok()).toBeTruthy()
  const result = await savedResultResponse.json()
  const action = { result_ids: [result.id], approve: true, comment: 'CODEX_TEST_E2E_闭环' }
  expect((await request.post(`${apiBase}/admin/results/submit`, { headers, data: action })).ok()).toBeTruthy()
  expect((await request.post(`${apiBase}/admin/results/review`, { headers, data: action })).ok()).toBeTruthy()
  expect((await request.post(`${apiBase}/sports-teacher/results/final-review`, { headers, data: action })).ok()).toBeTruthy()

  // Keep the public browser open before publishing; its 30-second polling must reveal the new result without reload.
  const publicPage = await context.newPage()
  await publicPage.goto(`/results?meet_id=${meet.id}`)
  await expect(publicPage.getByText(eventName, { exact: true })).toHaveCount(0)
  expect((await request.post(`${apiBase}/sports-teacher/results/publish`, { headers, data: action })).ok()).toBeTruthy()
  await expect(publicPage.getByText(eventName, { exact: true }).first()).toBeVisible({ timeout: 36_000 })
  await expect(publicPage.getByText(studentName, { exact: true }).first()).toBeVisible()

  // Promotion uses the published snapshot, then the activated student can see both result and promotion.
  const advanceResponse = await request.post(`${apiBase}/sports-teacher/event-registrations/advance`, {
    headers,
    data: { event_id: event.id, from_round_id: heat.id, to_round_id: semifinal.id, count: 1, alternates: 0 },
  })
  expect(advanceResponse.ok()).toBeTruthy()
  expect((await request.get(`${apiBase}/admin/results/export?event_id=${event.id}`, { headers })).ok()).toBeTruthy()
  expect((await request.post(`${apiBase}/auth/student-register`, { data: { student_no: studentNo, name: studentName } })).ok()).toBeTruthy()

  await page.goto('/login')
  await page.getByRole('button', { name: '学生' }).click()
  await page.getByPlaceholder('请输入学号').fill(studentNo)
  await page.getByPlaceholder('请输入密码').fill(`DF${studentNo}`)
  await page.getByRole('button', { name: '进入系统' }).click()
  await expect(page).toHaveURL(/\/app$/)
  await page.getByRole('button', { name: '我的成绩', exact: true }).click()
  await expect(page.getByText(eventName, { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: '我的赛事', exact: true }).click()
  await expect(page.getByText(eventName, { exact: true }).first()).toBeVisible()

  // Developer audit query closes the workflow with persistent operational evidence.
  const developerLogin = await request.post(`${apiBase}/auth/developer-login`, { data: { username: 'developer01', password: 'Dev123456!' } })
  const developerToken = (await developerLogin.json()).access_token
  const audits = await (await request.get(`${apiBase}/developer/audit-logs?page_size=200`, { headers: { Authorization: `Bearer ${developerToken}` } })).json()
  expect(audits.items.some((row: any) => row.action === 'PUBLISH_RESULT' && String(row.target_id) === String(result.id))).toBeTruthy()
})
