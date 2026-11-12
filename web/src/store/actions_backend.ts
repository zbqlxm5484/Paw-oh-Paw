// 백엔드에 있는 기능의 폼 처리. 가짜 서버 모드(--mode mock)가 아니면 BACKEND 우선순위로 등록돼, import 순서와 무관하게
// actions_impl.ts 보다 먼저 같은 주소를 받는다.
// 바이탈·진단 이력·메모·진료 기록(271)도 서버에 쓰고 그 반려견 차트를 다시 읽는다. 시연 기관은 '__local__' 로 actions_impl.ts 에 넘긴다.
import { ApiError } from '../api/client'
import { redirect, need_login, setLogin, current, currentStaff, type Go } from '../app/session'
import * as config from '../config'
import { on, f, petInputError, BACKEND, type Handler } from './actions'
import { api, MOCK, SEX_OUT, SIZE_OUT, STAGE_OUT, KIND_OUT, CAT_OUT, syncFromBackend, syncDogChart, toDog, tokenStore, isRemote, syncAdmin } from './backend'
import { db, dogOf, isoToday, resultOf } from './db'
import { remember } from './sessions_backend'
import { keepFiles } from './uploadRetry'
import { LEGAL } from '../legal/content'

/** 백엔드 처리 함수 등록: 로컬(시제품) 처리 함수보다 언제나 먼저 불린다 */
const onB = (pattern: string, h: Handler) => on(pattern, h, BACKEND)

const msg = (e: unknown): string => (e instanceof ApiError ? e.message : '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.')

/** 로그인 뒤 갈 곳(시제품 login 과 같다) */
async function enter(token: { access_token: string; expires_at: string; staff: { effective_role: string; role: string } }, toast = ''): Promise<Go> {
  tokenStore.set(token.access_token, token.expires_at)
  const sid = await syncFromBackend(token.staff as never)
  setLogin(sid)
  const s = token.staff
  if (s.role === 'ADMIN' || s.role === 'STAFF') {
    await syncAdmin()
    return redirect('/admin', toast)
  }
  if (s.effective_role === 'GUEST') return redirect('/expired', toast)
  return redirect('/home', toast)
}

if (!MOCK) {
  onB('/login', async (_p, fd) => {
    try {
      return await enter(await api.login(f(fd, 'login_id'), f(fd, 'password')))
    } catch (e) {
      return redirect('/login', msg(e))
    }
  })

  onB('/logout', () => {
    tokenStore.clear()
    setLogin(null)
    return redirect('/')
  })

  onB('/signup', async (_p, fd) => {
    if (!(f(fd, 't0') && f(fd, 't1') && f(fd, 't2'))) return redirect('/signup', '필수 약관에 동의해 주세요')
    if (f(fd, 'pw') !== f(fd, 'pw2')) return redirect('/signup', '비밀번호가 서로 다릅니다')
    try {
      // 약관 동의(192): 필수 셋은 위에서 확인했고, 버전은 약관 본문의 갱신일
      const terms = { version: LEGAL.terms.updated, service: true, privacy: true, device_location: true, marketing: !!f(fd, 't3') }
      const t = await api.signup({ code: f(fd, 'code'), login_id: f(fd, 'login_id'), password: f(fd, 'pw'), name: f(fd, 'name').trim(), email: f(fd, 'email').trim(), terms })
      return await enter(t, `${t.staff.institution.name} 담당자로 가입했습니다`)
    } catch (e) {
      return redirect('/signup', msg(e))
    }
  })

  onB('/forgot', async (_p, fd) => {
    try {
      await api.resetRequest(f(fd, 'login_id')) // 계정이 있든 없든 204. 링크는 메일로만 간다
      return redirect('/forgot?sent=1')
    } catch (e) {
      return redirect('/forgot', msg(e)) // 503 MAIL_UNAVAILABLE 등
    }
  })

  onB('/reset-password', async (_p, fd) => {
    const token = f(fd, 'token')
    if (f(fd, 'pw') !== f(fd, 'pw2')) return redirect(`/reset-password?token=${encodeURIComponent(token)}`, '8자 이상, 두 칸이 같게 입력해 주세요')
    try {
      await api.resetConfirm(token, f(fd, 'pw'))
      return redirect('/login', '비밀번호를 바꿨습니다. 새 비밀번호로 로그인해 주세요')
    } catch (e) {
      return redirect('/forgot', msg(e))
    }
  })

  onB('/account/profile', async (_p, fd) => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' } // 시연 기관은 actions_impl 이 처리
    try {
      await syncFromBackend(await api.updateMe({ name: f(fd, 'name').trim(), email: f(fd, 'email').trim() }))
      return redirect('/account', '저장했습니다')
    } catch (e) {
      return redirect('/account', msg(e))
    }
  })

  // 회원 탈퇴(192): 서버가 계정을 중지하면 토큰을 버리고 로그인 화면으로. 비밀번호 오류·마지막 계정(409 LAST_ACCOUNT)은 서버 문구 그대로
  onB('/account/withdraw', async (_p, fd) => {
    if (!current()) return need_login()
    try {
      await api.withdraw(f(fd, 'password'))
      tokenStore.clear()
      setLogin(null)
      return redirect('/login', '탈퇴했습니다. 그동안 이용해 주셔서 감사합니다')
    } catch (e) {
      return redirect('/account', msg(e))
    }
  })

  onB('/account/password', async (_p, fd) => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' }
    if (f(fd, 'pw') !== f(fd, 'pw2')) return redirect('/account', '새 비밀번호는 8자 이상, 현재와 다르게 입력해 주세요')
    try {
      await api.changePassword(f(fd, 'current_pw'), f(fd, 'pw'))
      // 서버가 그전에 받은 토큰을 이 요청에 쓴 것까지 끊는다(백엔드 명세 15.4 v1.48). 탈퇴처럼 토큰을 버리고 다시 로그인하게 한다
      tokenStore.clear()
      setLogin(null)
      return redirect('/login', '비밀번호를 바꿨습니다. 새 비밀번호로 로그인해 주세요')
    } catch (e) {
      return redirect('/account', msg(e))
    }
  })

  // 반려견 등록·수정: 백엔드 기관이면 서버에 저장하고, 서버에 없는 칸(동물번호·보호자 등)은 이 브라우저에 둔다
  onB('/dogs', async (_p, fd) => {
    const acct = current()
    if (!acct) return need_login()
    const next_url = f(fd, 'next_url') || '/home'
    if (!isRemote(acct.id)) return { to: '__local__' } // 시연 기관은 actions_impl 이 처리
    const name = f(fd, 'name').trim(), breed = f(fd, 'breed').trim(), kg = f(fd, 'kg').trim()
    if (!(name && breed && kg)) return redirect(next_url, '이름·견종·체중을 입력해 주세요')
    const size = f(fd, 'size'), sex = f(fd, 'sex') || 'm', focus = f(fd, 'focus'), birth = f(fd, 'birth').trim()
    const bad = petInputError(kg, birth)
    if (bad) return redirect(next_url, bad)
    const body: Record<string, unknown> = {
      name, breed, weight_kg: Number(kg), size_class: size in config.SIZE ? SIZE_OUT[size] : null,
      birth_year: birth ? Number(birth) : null, sex: SEX_OUT[sex] ?? null, rehab_start_date: f(fd, 'rehab') || null,
      focus_limb: focus in config.LIMB ? focus : null, memo: f(fd, 'memo').trim() || null,
    }
    const dog_id = f(fd, 'dog_id')
    // 동물번호·보호자·단계(271). 수정 때는 바뀐 칸만 보낸다(목록에서 읽은 반려견은 연락처 전체를 모를 수 있어서). 지울 때는 null
    const prev = dogOf(acct, dog_id)
    const extra: [string, string, string][] = [['chart_no', 'no', prev?.no ?? ''], ['owner_name', 'owner', prev?.owner ?? ''], ['owner_phone', 'phone', prev?.phone ?? '']]
    for (const [key, field, old] of extra) {
      if (!fd.has(field)) continue
      const v = f(fd, field).trim()
      if (prev ? v !== old : v) body[key] = v || null
    }
    const stage = f(fd, 'stage')
    if (stage in config.STAGE && (!prev || stage !== prev.stage)) body.stage = STAGE_OUT[stage]
    try {
      if (dogOf(acct, dog_id)) {
        const o = await api.updateDog(dog_id, { ...body, version: Number(f(fd, 'version') || dogOf(acct, dog_id)!.version) })
        await syncFromBackend()
        // 목록 응답에는 연락처 전체가 없어 수정 응답(상세 모양)으로 한 번 더 맞춘다
        const a = current()
        const i = a ? a.dogs.findIndex((x) => x.id === o.id) : -1
        if (a && i >= 0) a.dogs[i] = toDog(o, a.dogs[i])
        return redirect(next_url, '저장했습니다')
      }
      const o = await api.createDog(body)
      await syncFromBackend()
      const a = current()
      const i = a ? a.dogs.findIndex((x) => x.id === o.id) : -1
      if (a && i >= 0) a.dogs[i] = toDog(o, a.dogs[i])
      const sep = next_url.includes('?') ? '&' : '?'
      if (next_url.startsWith('/upload') || next_url.startsWith('/my')) return redirect(`${next_url}${sep}dog=${o.id}`, `${o.name} 등록을 마쳤습니다`)
      return redirect(`/dogs/${o.id}`, `${o.name} 등록을 마쳤습니다`)
    } catch (e) {
      if (e instanceof ApiError && e.code === 'DOG_MODIFIED') return redirect(next_url, '다른 담당자가 먼저 수정했습니다. 화면을 새로 불러온 뒤 다시 시도해 주세요.')
      return redirect(next_url, msg(e))
    }
  })

  // 기준 회차 지정: 서버 반려견의 baseline_session_id 로 저장한다(version 낙관적 잠금). 다른 담당자가 먼저 고쳤으면 다시 불러온다
  onB('/dogs/:dog_id/base', async (p, fd) => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' }
    const back = `/dogs/${p.dog_id}`
    const d = dogOf(acct, p.dog_id), r = resultOf(acct, f(fd, 'rid'))
    if (!d || !r || r.st === 'fail') return redirect(back)
    try {
      await api.updateDog(d.id, { baseline_session_id: r.id, version: d.version })
      await syncFromBackend()
      return redirect(back, `${r.date} 회차를 기준으로 정했습니다`)
    } catch (e) {
      if (e instanceof ApiError && e.code === 'DOG_MODIFIED') {
        await syncFromBackend().catch(() => undefined)
        return redirect(back, '다른 담당자가 먼저 수정해서 새로 불러왔습니다. 다시 눌러 주세요')
      }
      return redirect(back, msg(e))
    }
  })

  // 측정: 회차를 열고 영상을 올린 뒤 측정을 끝낸다(분석은 서버). 분석 중 화면에서 서버 상태를 따라가 결과로 넘어간다
  onB('/analyze', async (_p, fd) => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' }
    const dog = f(fd, 'dog'), weight = f(fd, 'weight').trim()
    if (!dogOf(acct, dog)) return redirect('/upload', '반려견을 골라 주세요')
    const files = fd.getAll('files').filter((x): x is File => x instanceof File && !!x.name)
    // 폰으로 촬영(QR)으로 이미 연 회차. 폰에서 올린 영상이 있으면 이 브라우저에서 고른 파일이 없어도 된다
    const phoneSid = f(fd, 'sid')
    const phoneSess = phoneSid ? await api.session(phoneSid).catch(() => null) : null
    // QR 회차가 다른 반려견 것이면 그 회차로 올리지 않는다
    if (phoneSess && phoneSess.dog_id !== dog) return redirect(`/upload?dog=${dog}`, 'QR 로 연 회차가 다른 반려견의 회차입니다. 화면을 새로 불러온 뒤 다시 시도해 주세요')
    const phoneShots = phoneSess?.shots.length ?? 0
    if (!files.length && !phoneShots) return redirect(`/upload?dog=${dog}`, '보행 영상을 1개 이상 올려 주세요')
    // 오늘 바이탈(선택): 적은 칸만 그날 바이탈로 저장한다(PUT /dogs/{id}/vitals/{오늘}, 적은 값만 바뀜)
    const vt = { temp_c: f(fd, 'temp').trim(), heart_rate: f(fd, 'hr').trim(), sbp: f(fd, 'sbp').trim(), dbp: f(fd, 'dbp').trim() }
    if ([weight, ...Object.values(vt)].some((v) => v !== '' && !Number.isFinite(Number(v)))) {
      keepFiles(dog, files)
      return redirect(`/upload?dog=${dog}`, '체중·바이탈은 숫자로 적어 주세요')
    }
    const vitalBody = Object.fromEntries(Object.entries({ weight_kg: weight, ...vt }).filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)]))
    const hasVital = Object.keys(vt).some((k) => vt[k as keyof typeof vt] !== '')
    // 회차 열기. 이미 측정 중인 회차가 있으면(앞서 업로드가 끊긴 경우 등) 그 회차에 이어서 올린다
    let sid = phoneSid, created = false
    if (!sid) {
      try {
        sid = (await api.startSession(dog, weight ? { weight_kg: Number(weight) } : {})).id
        created = true
      } catch (e) {
        const open = e instanceof ApiError && e.code === 'SESSION_ALREADY_OPEN' ? (await api.dog(dog).catch(() => null))?.open_session_id : null
        if (!open) return redirect(`/upload?dog=${dog}`, msg(e))
        sid = open
      }
    }
    // 바이탈은 업로드를 막지 않는다. 저장하지 못하면 알려만 준다
    let vitalNote = ''
    if (hasVital) await api.putVital(dog, isoToday(), vitalBody).catch((e) => { vitalNote = ` (바이탈은 저장하지 못했습니다: ${msg(e)})` })
    const n = Math.min(files.length, config.MAX_SHOTS - phoneShots)
    let failedName = ''
    try {
      for (const file of files.slice(0, n)) {
        failedName = file.name
        await api.uploadShot(sid, file)
      }
    } catch (e) {
      // 이번에 연 회차는 지운다(413·400·연결 끊김). 남겨 두면 그 반려견이 '측정 중'에 갇힌다. 이어서 쓰던 회차는 그대로 둬 다음 업로드가 이어 쓴다
      if (created) await api.cancelSession(sid).catch(() => undefined)
      await syncFromBackend().catch(() => undefined)
      // 고른 영상은 업로드 화면으로 돌려보내 다시 고르지 않게 하고, 어느 파일에서 왜 멈췄는지 알린다
      keepFiles(dog, files)
      return redirect(`/upload?dog=${dog}`, `${failedName ? `'${failedName}' 올리기 실패: ` : ''}${msg(e)}`)
    }
    try {
      await api.completeSession(sid)
    } catch (e) {
      // 폰 앱에서 먼저 분석을 시작했으면 회차가 이미 닫혀 있다. 실패가 아니라 그 분석을 따라간다
      if (!(e instanceof ApiError && e.code === 'SESSION_CLOSED')) return redirect(`/upload?dog=${dog}`, msg(e))
    }
    remember(acct, { id: sid, inst: acct.id, dog, started: Date.now(), n: n + phoneShots, w: weight || dogOf(acct, dog)!.kg, by: currentStaff()?.name ?? '' })
    return redirect(`/analyzing/${sid}`, (created ? '' : '측정 중이던 회차에 이어서 올렸습니다') + vitalNote)
  })

  // ── 반려견 차트(271): 메모·진료 기록·바이탈·진단 이력. 쓴 담당자는 서버가 로그인한 사람으로 적는다(작성자 칸은 보내지 않는다) ──
  /** 서버에 쓰고 차트를 다시 읽은 뒤 돌아간다. 실패하면 서버 문구 그대로 */
  const chartDo = async (dogId: string, back: string, run: () => Promise<string>): Promise<Go> => {
    const acct = current()!
    try {
      const toast = await run()
      await syncDogChart(acct.id, dogId).catch(() => undefined)
      return redirect(back, toast)
    } catch (e) {
      await syncDogChart(acct.id, dogId).catch(() => undefined) // 여러 번 부르다 중간에 실패했으면 된 데까지 보인다
      return redirect(back, msg(e))
    }
  }
  const badNum = (...vs: string[]) => vs.some((v) => v !== '' && !Number.isFinite(Number(v)))

  onB('/dogs/:dog_id/notes', async (p, fd) => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' }
    const d = dogOf(acct, p.dog_id)
    const next_url = f(fd, 'next_url')
    const back = next_url.startsWith('/results/') || next_url.startsWith('/dogs/') ? next_url : `/dogs/${p.dog_id}`
    if (!d) return redirect('/home')
    const note_id = f(fd, 'note_id'), text = f(fd, 'text').trim(), important = !!f(fd, 'important'), visit = !!f(fd, 'visit')
    // 방문일(271): 지난 방문의 기록도 그 날짜로 쓴다. 미래는 받지 않는다
    const today = isoToday()
    const visited_on = f(fd, 'visit_day') || today
    if (visited_on > today) return redirect(back, '오늘 이후 날짜로는 기록할 수 없습니다')
    if (note_id && f(fd, 'delete')) {
      return chartDo(d.id, back, async () => {
        await api.deleteNote(note_id)
        return '지웠습니다'
      })
    }
    const soap = (['S', 'O', 'A', 'P'] as const).map((k) => [k, f(fd, k.toLowerCase()).trim()] as [string, string]).filter(([, v]) => v)
    const r = resultOf(acct, f(fd, 'rid'))
    const session_id = r && r.dog === d.id ? r.id : undefined
    const soapBatch = () => api.addNotes(d.id, { session_id, visited_on, notes: soap.map(([k, v], i) => ({ category: k, body: v, important: important && i === 0 })) })
    if (note_id) {
      if (!text) return redirect(back, '내용을 적어 주세요')
      return chartDo(d.id, back, async () => {
        await api.updateNote(note_id, { body: text })
        return '고쳤습니다. 이전 내용은 이력에 남습니다'
      })
    }
    if (visit) {
      // 오늘 방문 기록: 바이탈은 방문마다 반드시 잰다(11-02). 오늘 이미 잰 값이 있으면 바꾼다
      // 지난 방문은 그날 바이탈을 안 쟀을 수 있어 비워도 된다(적으면 다 적어야 한다)
      const vals = ['kg', 'temp', 'hr', 'sbp', 'dbp'].map((k) => f(fd, k).trim())
      const noVital = visited_on !== today && !vals.some(Boolean)
      if (!noVital && !vals.every(Boolean)) return redirect(back, '바이탈(체중·체온·심박·혈압)을 모두 적어 주세요')
      if (badNum(...vals)) return redirect(back, '바이탈은 숫자로 적어 주세요')
      if (noVital && !soap.length) return redirect(back, '바이탈이나 진료 기록을 적어 주세요')
      const [kg, temp, hr, sbp, dbp] = vals.map(Number)
      return chartDo(d.id, back, async () => {
        if (!noVital) await api.putVital(d.id, visited_on, { weight_kg: kg, temp_c: temp, heart_rate: hr, sbp, dbp })
        if (!soap.length) return '바이탈을 기록했습니다'
        await soapBatch()
        return '기록을 남겼습니다'
      })
    }
    if (soap.length) {
      return chartDo(d.id, back, async () => {
        await soapBatch()
        return '기록을 남겼습니다'
      })
    }
    if (!text) return redirect(back, '내용을 적어 주세요')
    const cat = f(fd, 'cat') || 'O'
    const category = CAT_OUT[cat] ?? 'OTHER'
    return chartDo(d.id, back, async () => {
      await api.addNote(d.id, { category, body: text, important, session_id, visited_on })
      return cat in config.SOAP ? '기록을 남겼습니다' : '메모를 남겼습니다'
    })
  })

  // 바이탈 한 날짜 저장·고치기·지우기. 저장은 적은 값만 보낸다(빈 칸은 그대로 둔다)
  onB('/dogs/:dog_id/vitals', async (p, fd) => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' }
    const d = dogOf(acct, p.dog_id)
    if (!d) return redirect('/home')
    const day = f(fd, 'day') || isoToday()
    const next_url = f(fd, 'next_url')
    const back = next_url.startsWith('/dogs/') ? next_url : `/dogs/${p.dog_id}?v=${day}`
    if (f(fd, 'delete')) {
      return chartDo(d.id, back, async () => {
        await api.deleteVital(d.id, day)
        return '그날 바이탈을 지웠습니다'
      })
    }
    const [kg, temp, hr, sbp, dbp] = ['kg', 'temp', 'hr', 'sbp', 'dbp'].map((k) => f(fd, k).trim())
    if (![kg, temp, hr, sbp, dbp].some(Boolean)) return redirect(back, '값을 하나 이상 적어 주세요')
    if (badNum(kg, temp, hr, sbp, dbp)) return redirect(back, '바이탈은 숫자로 적어 주세요')
    if (!!sbp !== !!dbp) return redirect(back, '혈압은 수축기·이완기를 함께 적어 주세요')
    const body: Record<string, number> = {}
    if (kg) body.weight_kg = Number(kg)
    if (temp) body.temp_c = Number(temp)
    if (hr) body.heart_rate = Number(hr)
    if (sbp) {
      body.sbp = Number(sbp)
      body.dbp = Number(dbp)
    }
    return chartDo(d.id, back, async () => {
      await api.putVital(d.id, day, body)
      return '바이탈을 기록했습니다'
    })
  })

  const historyBody = (fd: FormData) => {
    const k = f(fd, 'kind')
    const site = f(fd, 'site')
    return {
      occurred_on: f(fd, 'day') || isoToday(), kind: KIND_OUT[k] ?? 'DIAGNOSIS', title: f(fd, 'title').trim(),
      site: site in config.SITE ? site : null, clinician: f(fd, 'by').trim() || null,
    }
  }

  onB('/dogs/:dog_id/history', async (p, fd) => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' }
    const d = dogOf(acct, p.dog_id)
    const back = `/dogs/${p.dog_id}?tab=dx`
    if (!d) return redirect('/home')
    const b = historyBody(fd)
    if (!b.title) return redirect(back, '내용을 적어 주세요')
    const stage = f(fd, 'stage')
    return chartDo(d.id, back, async () => {
      await api.addHistory(d.id, { ...b, ...(stage in config.STAGE && stage !== d.stage ? { stage: STAGE_OUT[stage] } : {}) })
      return '진단 이력에 남겼습니다'
    })
  })

  // 진단 이력 한 줄 고치기·지우기(!130). 반려견 단계는 바뀌지 않는다
  onB('/dogs/:dog_id/history/:hid', async (p, fd) => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' }
    const d = dogOf(acct, p.dog_id)
    const back = `/dogs/${p.dog_id}?tab=dx`
    if (!d) return redirect('/home')
    if (f(fd, 'delete')) {
      return chartDo(d.id, back, async () => {
        await api.deleteHistory(d.id, p.hid)
        return '진단 이력에서 지웠습니다'
      })
    }
    const b = historyBody(fd)
    if (!b.title) return redirect(`${back}&hedit=${encodeURIComponent(p.hid)}`, '내용을 적어 주세요')
    return chartDo(d.id, back, async () => {
      await api.updateHistory(d.id, p.hid, b)
      return '진단 이력을 고쳤습니다'
    })
  })

  // ── 크림오프 관리(백엔드 /admin) ──
  const adminOnly = (): Go | null => (currentStaff()?.role === 'ADMIN' ? null : redirect('/admin', '조회 전용 계정입니다'))
  const after = async (toast: string): Promise<Go> => {
    await syncAdmin()
    return redirect('/admin', toast)
  }
  onB('/admin/institutions', async (_p, fd) => {
    const no = adminOnly()
    if (no) return no
    try {
      await api.createInstitution({ name: f(fd, 'name').trim(), contract_ends_at: f(fd, 'ends') || null })
      return await after('기관을 만들었습니다')
    } catch (e) {
      return redirect('/admin', msg(e))
    }
  })
  onB('/admin/institutions/:inst', async (p, fd) => {
    const no = adminOnly()
    if (no) return no
    try {
      await api.updateInstitution(p.inst, { contract_ends_at: f(fd, 'ends') || null })
      return await after('계약 종료일을 바꿨습니다')
    } catch (e) {
      return redirect('/admin', msg(e))
    }
  })
  onB('/admin/institutions/:inst/codes', async (p, fd) => {
    const no = adminOnly()
    if (no) return no
    try {
      await api.createDeviceCode(p.inst, { note: f(fd, 'note') || undefined }) // 쓸 수 있는 코드가 있으면 409 DEVICE_CODE_EXISTS(회수한 뒤 발급)
      return await after('디바이스 코드를 발급했습니다')
    } catch (e) {
      return redirect('/admin', msg(e))
    }
  })
  onB('/admin/codes/:cid', async (p, fd) => {
    const no = adminOnly()
    if (no) return no
    try {
      if (f(fd, 'revoke')) await api.revokeDeviceCode(p.cid)
      else await api.updateDeviceCode(p.cid, { note: f(fd, 'note') || null })
      return await after(f(fd, 'revoke') ? '코드를 회수했습니다. 새 코드는 발급 버튼으로' : '메모를 바꿨습니다')
    } catch (e) {
      return redirect('/admin', msg(e))
    }
  })
  onB('/admin/staff/:sid', async (p) => {
    const no = adminOnly()
    if (no) return no
    const s = db.staff[p.sid]
    try {
      await api.updateStaff(p.sid, { is_active: !(s && s.active) })
      return await after(s && s.active ? '계정을 중지했습니다' : '계정을 다시 쓸 수 있게 했습니다')
    } catch (e) {
      return redirect('/admin', msg(e))
    }
  })

  // 반려견 삭제: 서버 휴지통으로 보낸다(DELETE /dogs/{id}). 예전에는 브라우저에서만 지워 새로 불러오면 다시 나타났다
  onB('/dogs/:dog_id/delete', async (p) => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' }
    const d = dogOf(acct, p.dog_id)
    if (!d) return redirect('/my')
    try {
      await api.deleteDog(d.id)
    } catch (e) {
      return redirect(`/dogs/${d.id}`, msg(e))
    }
    acct.dogs = acct.dogs.filter((x) => x.id !== d.id)
    acct.results = acct.results.filter((r) => r.dog !== d.id)
    acct.jobs = acct.jobs.filter((j) => j.dog !== d.id)
    return redirect('/my', `${d.name} 정보를 삭제했습니다`)
  })

  // 분석 완료 알림 켜기·끄기: 담당자 설정(PATCH /auth/me notif_on)
  onB('/my/notif', async () => {
    const acct = current()
    if (!acct) return need_login()
    if (!isRemote(acct.id)) return { to: '__local__' }
    try {
      const me = await api.updateMe({ notif_on: !acct.notif_on })
      acct.notif_on = me.notif_on ?? !acct.notif_on
    } catch (e) {
      return redirect('/my', msg(e))
    }
    return redirect('/my', acct.notif_on ? '분석 완료 알림을 켰습니다' : '분석 완료 알림을 껐습니다')
  })
}
