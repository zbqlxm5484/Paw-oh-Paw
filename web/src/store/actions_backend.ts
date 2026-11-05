// 백엔드에 있는 기능의 폼 처리. 가짜 서버 모드(--mode mock)가 아니면 BACKEND 우선순위로 등록돼, import 순서와 무관하게
// actions_impl.ts 보다 먼저 같은 주소를 받는다.
// 백엔드에 없는 기능(메모·바이탈·진단 이력·기준 회차·삭제 등)은 등록하지 않아 actions_impl.ts(브라우저 저장소)가 그대로 받는다.
import { ApiError } from '../api/client'
import { redirect, need_login, setLogin, current, currentStaff, type Go } from '../app/session'
import * as config from '../config'
import { on, f, BACKEND, type Handler } from './actions'
import { api, MOCK, SEX_OUT, SIZE_OUT, syncFromBackend, tokenStore, isRemote, syncAdmin } from './backend'
import { db, dogOf, resultOf } from './db'
import { remember } from './sessions_backend'

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
    if (f(fd, 'pw') !== f(fd, 'pw2')) return redirect('/signup', '비밀번호가 서로 달라요')
    try {
      const t = await api.signup({ code: f(fd, 'code'), login_id: f(fd, 'login_id'), password: f(fd, 'pw'), name: f(fd, 'name').trim(), email: f(fd, 'email').trim() })
      return await enter(t, `${t.staff.institution.name} 담당자로 가입했어요`)
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
      return redirect('/login', '비밀번호를 바꿨어요. 새 비밀번호로 로그인해 주세요')
    } catch (e) {
      return redirect('/forgot', msg(e))
    }
  })

  onB('/account/profile', async (_p, fd) => {
    if (!current()) return need_login()
    try {
      await syncFromBackend(await api.updateMe({ name: f(fd, 'name').trim(), email: f(fd, 'email').trim() }))
      return redirect('/account', '저장했어요')
    } catch (e) {
      return redirect('/account', msg(e))
    }
  })

  onB('/account/password', async (_p, fd) => {
    if (!current()) return need_login()
    if (f(fd, 'pw') !== f(fd, 'pw2')) return redirect('/account', '새 비밀번호는 8자 이상, 현재와 다르게 입력해 주세요')
    try {
      await api.changePassword(f(fd, 'current_pw'), f(fd, 'pw'))
      return redirect('/account', '비밀번호를 바꿨어요')
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
    const body: Record<string, unknown> = {
      name, breed, weight_kg: Number(kg), size_class: size in config.SIZE ? SIZE_OUT[size] : null,
      birth_year: birth ? Number(birth) : null, sex: SEX_OUT[sex] ?? null, rehab_start_date: f(fd, 'rehab') || null,
      focus_limb: focus in config.LIMB ? focus : null, memo: f(fd, 'memo').trim() || null,
    }
    const dog_id = f(fd, 'dog_id')
    try {
      if (dogOf(acct, dog_id)) {
        await api.updateDog(dog_id, { ...body, version: Number(f(fd, 'version') || dogOf(acct, dog_id)!.version) })
        await syncFromBackend()
        return redirect(next_url, '저장했어요')
      }
      const o = await api.createDog(body)
      await syncFromBackend()
      const sep = next_url.includes('?') ? '&' : '?'
      if (next_url.startsWith('/upload') || next_url.startsWith('/my')) return redirect(`${next_url}${sep}dog=${o.id}`, `${o.name} 등록을 마쳤어요`)
      return redirect(`/dogs/${o.id}`, `${o.name} 등록을 마쳤어요`)
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
      return redirect(back, `${r.date} 회차를 기준으로 정했어요`)
    } catch (e) {
      if (e instanceof ApiError && e.code === 'DOG_MODIFIED') {
        await syncFromBackend().catch(() => undefined)
        return redirect(back, '다른 담당자가 먼저 수정해서 새로 불러왔어요. 다시 눌러 주세요')
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
    const phoneShots = phoneSid ? (await api.session(phoneSid).catch(() => null))?.shots.length ?? 0 : 0
    if (!files.length && !phoneShots) return redirect(`/upload?dog=${dog}`, '보행 영상을 1개 이상 올려 주세요')
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
    const n = Math.min(files.length, config.MAX_SHOTS - phoneShots)
    try {
      for (const file of files.slice(0, n)) await api.uploadShot(sid, file)
    } catch (e) {
      // 이번에 연 회차는 지운다(413·400·연결 끊김). 남겨 두면 그 반려견이 '측정 중'에 갇힌다. 이어서 쓰던 회차는 그대로 둬 다음 업로드가 이어 쓴다
      if (created) await api.cancelSession(sid).catch(() => undefined)
      await syncFromBackend().catch(() => undefined)
      return redirect(`/upload?dog=${dog}`, msg(e))
    }
    try {
      await api.completeSession(sid)
    } catch (e) {
      return redirect(`/upload?dog=${dog}`, msg(e))
    }
    remember(acct, { id: sid, inst: acct.id, dog, started: Date.now(), n: n + phoneShots, w: weight || dogOf(acct, dog)!.kg, by: currentStaff()?.name ?? '' })
    return redirect(`/analyzing/${sid}`, created ? '' : '측정 중이던 회차에 이어서 올렸어요')
  })

  // ── 크림오프 관리(백엔드 /admin) ──
  const adminOnly = (): Go | null => (currentStaff()?.role === 'ADMIN' ? null : redirect('/admin', '조회 전용 계정이에요'))
  const after = async (toast: string): Promise<Go> => {
    await syncAdmin()
    return redirect('/admin', toast)
  }
  onB('/admin/institutions', async (_p, fd) => {
    const no = adminOnly()
    if (no) return no
    try {
      await api.createInstitution({ name: f(fd, 'name').trim(), contract_ends_at: f(fd, 'ends') || null })
      return await after('기관을 만들었어요')
    } catch (e) {
      return redirect('/admin', msg(e))
    }
  })
  onB('/admin/institutions/:inst', async (p, fd) => {
    const no = adminOnly()
    if (no) return no
    try {
      await api.updateInstitution(p.inst, { contract_ends_at: f(fd, 'ends') || null })
      return await after('계약 종료일을 바꿨어요')
    } catch (e) {
      return redirect('/admin', msg(e))
    }
  })
  onB('/admin/institutions/:inst/codes', async (p, fd) => {
    const no = adminOnly()
    if (no) return no
    try {
      await api.createDeviceCode(p.inst, { max_accounts: Number(f(fd, 'max_accounts') || 3), note: f(fd, 'note') || undefined })
      return await after('디바이스 코드를 발급했어요')
    } catch (e) {
      return redirect('/admin', msg(e))
    }
  })
  onB('/admin/codes/:cid', async (p, fd) => {
    const no = adminOnly()
    if (no) return no
    try {
      if (f(fd, 'revoke')) await api.revokeDeviceCode(p.cid)
      else await api.updateDeviceCode(p.cid, { max_accounts: Number(f(fd, 'max_accounts') || 3) })
      return await after(f(fd, 'revoke') ? '코드를 회수했어요' : '계정 상한을 바꿨어요')
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
      return await after(s && s.active ? '계정을 중지했어요' : '계정을 다시 쓸 수 있게 했어요')
    } catch (e) {
      return redirect('/admin', msg(e))
    }
  })
}
