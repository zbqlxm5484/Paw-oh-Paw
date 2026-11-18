// upload.html + static/upload.js + main.py upload(): 반려견 고르기, 영상 16개까지 차례로 첨부(끌어 놓기 · 고르기), 분석 시작
import { useFirstFrames, useShotVideos } from '../app/thumbs'
import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import { cancelPhoneSession, dropEmptySession, openSession, PhoneCaptureModal, shotAction, usePhoneShots } from './parts/PhoneCapture'
import { MOCK, isRemote } from '../store/backend'
import { api, ApiError } from '../api/client'
import { useNavigate } from 'react-router-dom'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, staticUrl, usePage, useTitle } from '../app/page'
import { redirect, setToast, type Go } from '../app/session'
import { MAX_SHOTS } from '../config'
import { dogOf } from '../store/db'
import { avatar } from '../views/views'
import { GuideModal, PetModal } from './parts/Modals'
import { takeFiles } from '../store/uploadRetry'
import { useUploadProgress } from '../store/uploadProgress'

/** 서버의 RedirectResponse: 지금 주소를 바꿔 치운다 */
function useRedirect(g: Go | null) {
  const navigate = useNavigate()
  useEffect(() => {
    if (!g) return
    if (g.toast) setToast(g.toast)
    navigate(g.to, { replace: true })
  })
}

const SAMPLE = staticUrl('assets/landing-walk.mp4')
const VITALS: [string, string, string][] = [['temp', '체온 ℃', '38.6'], ['hr', '심박 bpm', '92'], ['sbp', '수축기 mmHg', '140'], ['dbp', '이완기 mmHg', '85']]

export default function Upload() {
  const { acct, me, toast, query } = usePage({ login: true })
  useTitle('보행 영상 분석')
  const dogQ = query.get('dog') ?? ''
  const demoQ = Math.max(0, Math.min(parseInt(query.get('demo') ?? '0', 10) || 0, 16))
  // 처음 고른 반려견(주소의 dog, 없으면 첫 반려견). 목록 순서는 처음 그릴 때 정해지고(고른 반려견이 맨 위) 바뀌지 않는다
  const [first] = useState(() => (acct ? dogOf(acct, dogQ) || acct.dogs[0] : undefined))
  const [selId, setSelId] = useState(first ? first.id : '')
  // 업로드가 실패해 돌아왔으면 그때 고른 영상을 다시 채운다
  const [files, setFiles] = useState<File[]>(() => takeFiles(first ? first.id : ''))
  const [demo, setDemo] = useState(demoQ)
  const [filt, setFilt] = useState('')
  // 폰으로 촬영: 먼저 연 회차와 QR 창. 폰에서 올라온 영상 수는 회차를 몇 초마다 읽어 센다
  const [phoneSid, setPhoneSid] = useState('')
  const [showQr, setShowQr] = useState(false)
  const { shots: phoneShots, reload: reloadPhone } = usePhoneShots(phoneSid)
  const phoneN = phoneShots.length
  // 첨부하는 즉시 올리기(314): 서버 기관이면 영상을 칸에 넣는 순간 회차를 열고 뒤에서 차례로 올린다.
  // '분석 시작'을 누를 때는 이미 올라가 있어 바로 분석 화면으로 넘어간다. 시연 기관·mock 은 예전처럼 누를 때 처리한다.
  // files = 아직 올리지 않은 영상(올릴 차례를 기다리는 줄), sent = 이 화면에서 올린 영상(서버 촬영 id 와 원본 파일)
  const pre = !MOCK && !!acct && isRemote(acct.id)
  const [sent, setSent] = useState<{ id: string; file: File }[]>([])
  const [upFile, setUpFile] = useState<File | null>(null) // 지금 올리는 영상
  // 다 올라가기 전에 '분석 시작'을 눌렀으면 남은 영상을 다 올린 뒤 스스로 제출한다(total = 이 화면에서 올리는 영상 수)
  const [autoStart, setAutoStart] = useState<{ total: number; fails: number } | null>(null)
  const gen = useRef(0) // 반려견을 바꾸거나 회차를 취소하면 올린다. 그 전에 시작한 업로드의 결과는 버린다
  const upBusy = useRef(false)
  const fails = useRef(0)
  const reloadRef = useRef(reloadPhone)
  reloadRef.current = reloadPhone
  const mine = useMemo(() => new Map(sent.map((s) => [s.id, s.file])), [sent])
  // 올렸지만 회차 조회(3초마다)에 아직 안 잡힌 영상. 그사이 칸이 비어 보이지 않게 이 화면이 들고 있는 파일로 채운다
  const seen = useRef(new Set<string>())
  for (const p of phoneShots) seen.current.add(p.id)
  const pend = sent.filter((s) => !seen.current.has(s.id)).map((s) => s.file)
  // 폰 등 다른 곳에서 올라온 영상 수(있으면 이 화면이 회차를 마음대로 지우지 않는다)
  const foreignN = phoneShots.filter((p) => !mine.has(p.id)).length
  // 이번 화면에서 새로 연 회차인지(이어 쓰는 회차면 원래 있던 영상도 센다), 분석을 시작했는지
  const [phoneCreated, setPhoneCreated] = useState(false)
  const leave = useRef({ sid: '', created: false, n: 0, ours: false, submitted: false })
  leave.current = { ...leave.current, sid: phoneSid, created: phoneCreated, n: phoneN, ours: pre && !foreignN }
  // 분석을 시작하지 않고 화면을 떠나면 새로 연 회차를 지운다: 영상이 없거나, 이 화면에서 올린 영상뿐일 때(폰에서 올린 영상이 있으면 남긴다)
  useEffect(() => () => {
    const l = leave.current
    gen.current++
    if (l.sid && l.created && !l.submitted && (!l.n || l.ours)) dropEmptySession(l.sid)
  }, [])
  // 줄 맨 앞 영상을 올린다. 하나가 끝나면 다음 영상으로 이어진다(올린 순서 = 촬영 번호)
  useEffect(() => {
    if (!pre || upBusy.current || !files.length) return
    const file = files[0], g = gen.current
    upBusy.current = true
    setUpFile(file)
    void (async () => {
      let opened = !!phoneSid
      try {
        let sid = phoneSid
        if (!sid) {
          const weight = (document.querySelector('input[name=weight]') as HTMLInputElement | null)?.value.trim() ?? ''
          if (weight && !Number.isFinite(Number(weight))) throw new Error('체중은 숫자로 적어 주세요')
          const o = await openSession(selId, weight)
          if (g !== gen.current) {
            if (o.created) dropEmptySession(o.id)
            return
          }
          sid = o.id
          opened = true
          setPhoneSid(o.id)
          setPhoneCreated(o.created)
        }
        const shot = await api.uploadShot(sid, file)
        if (g !== gen.current) return
        setSent((s) => [...s, { id: shot.id, file }])
        setFiles((fs) => fs.filter((x) => x !== file))
        reloadRef.current()
      } catch (e) {
        if (g !== gen.current) return
        fails.current++
        const m = e instanceof Error ? e.message : '올리지 못했습니다'
        // 영상 하나가 검사에 걸린 것이면 그 영상만 빼고 이어 간다. 회차를 못 열었거나 연결이 끊겼으면 남은 영상을 모두 내려놓는다
        const one = opened && e instanceof ApiError && e.code !== 'SESSION_CLOSED' && e.code !== 'NOT_FOUND'
        if (one) {
          setFiles((fs) => fs.filter((x) => x !== file))
          window.ppToast(`'${file.name}' 올리기 실패: ${m}`)
        } else {
          setFiles([])
          window.ppToast(opened ? `영상을 올리지 못했습니다: ${m}. 영상을 다시 넣어 주세요` : m)
        }
      } finally {
        upBusy.current = false
        setUpFile(null)
      }
    })()
  }, [pre, files, upFile, phoneSid, selId])
  // 남은 영상이 다 올라가면 제출한다. 기다리는 동안 실패한 영상이 있었으면 멈추고 사용자가 보고 다시 누르게 한다
  useEffect(() => {
    if (!autoStart || files.length || upFile) return
    setAutoStart(null)
    if (fails.current !== autoStart.fails) return
    ;(document.getElementById('upForm') as HTMLFormElement | null)?.requestSubmit()
  }, [autoStart, files, upFile])
  // '분석 시작' 뒤 영상을 올리는 동안의 진행(올리는 중이 아니면 null)
  const sending = useUploadProgress()
  const [over, setOver] = useState({ drop: false, slot: false })
  const picker = useRef<HTMLInputElement>(null)
  const video = useRef<HTMLVideoElement>(null)
  const urls = useRef(new WeakMap<File, string>())
  const localFiles = useMemo(() => [...sent.map((s) => s.file), ...files], [sent, files])
  const thumbs = useFirstFrames(localFiles)
  // 이 화면에서 올린 영상은 들고 있는 파일로 썸네일을 그리므로 서버 영상 주소를 묻지 않는다
  const foreignShots = useMemo(() => phoneShots.filter((p) => !mine.has(p.id)), [phoneShots, mine])
  const phoneVideos = useShotVideos(foreignShots)
  // 폰에서 16개가 다 올라오면 QR 창을 닫는다(폰도 촬영 화면을 닫는다)
  useEffect(() => {
    if (phoneN >= MAX_SHOTS && showQr) {
      setShowQr(false)
      // 이 화면에서 올린 영상이 섞여 있으면 폰에서 올라왔다고 알리지 않는다
      if (foreignN >= MAX_SHOTS) window.ppToast(`폰에서 영상 ${MAX_SHOTS}개가 모두 올라왔습니다`)
    }
  }, [phoneN, foreignN, showQr])

  const go: Go | null = acct && !acct.dogs.length ? redirect('/home?modal=pet', '먼저 반려견을 등록해 주세요') : null
  useRedirect(go)

  // 가장 최근에 올린 영상을 미리 보기. 웹·폰(QR) 어디서 올렸든 같다.
  // 올릴 차례를 기다리는 파일이 있으면 그중 마지막, 없으면 서버 촬영 중 순번이 가장 큰 것(이 탭에서 올린 건 들고 있는 파일, 폰 영상은 서버 주소).
  // 견본 영상은 ?demo= 시연 때만 쓴다. 폰 영상 주소를 받기 전에는 바로 앞 영상을 보인다
  const blobUrl = (f: File) => {
    let u = urls.current.get(f)
    if (!u) {
      u = URL.createObjectURL(f)
      urls.current.set(f, u)
    }
    return u
  }
  let preview: string | undefined
  if (files.length) preview = blobUrl(files[files.length - 1])
  // 방금 올렸지만 서버 조회에 아직 안 잡힌 파일이 서버 촬영보다 새것이다
  else if (pend.length) preview = blobUrl(pend[pend.length - 1])
  else {
    for (let i = phoneShots.length - 1; i >= 0 && !preview; i--) {
      const own = mine.get(phoneShots[i].id)
      preview = own ? blobUrl(own) : phoneVideos[phoneShots[i].id]
    }
    if (!preview && !phoneN) preview = SAMPLE
  }
  useEffect(() => {
    const v = video.current
    if (v) v.muted = true
  })

  if (!acct || go || !first) return null
  const sel = dogOf(acct, selId) || first
  const order = [first, ...acct.dogs.filter((d) => d.id !== first.id)] // 고른 반려견을 맨 위에
  const dogs = order.map((d) => ({ id: d.id, init: d.name.slice(0, 1), name: d.name, no: d.no, breed: d.breed || '견종 미입력', kg: d.kg, ...avatar(d.id === sel.id) }))
  const locals = [...pend, ...files] // 서버 조회에 아직 안 잡힌 영상 + 올릴 차례를 기다리는 영상
  const n = locals.length + phoneN || demo
  const max = MAX_SHOTS
  // 덮개에 보일 진행: 남은 영상을 올리며 기다리는 중(autoStart)이거나, 제출한 뒤 처리 중(sending)
  const wait = autoStart ? { done: Math.min(sent.length, autoStart.total), total: autoStart.total } : sending

  // 3. 영상 첨부
  const add = (list: FileList | File[]) => {
    if (n >= max) {
      window.ppToast('영상 ' + max + '개를 모두 첨부했습니다')
      return
    }
    let added = 0
    let bad = 0
    const next = files.slice()
    Array.prototype.forEach.call(list, (f: File) => {
      const ok = /^video\//.test(f.type) || /\.(mp4|mov|m4v)$/i.test(f.name)
      if (!ok) {
        bad++
        return
      }
      if (next.length + pend.length + phoneN < max) { // 이미 올라간 영상까지 합쳐 16개
        next.push(f)
        added++
      }
    })
    if (added) setDemo(0)
    if (bad && !added) return window.ppToast('영상 파일(MP4/MOV)만 올릴 수 있습니다')
    if (added) window.ppToast(added === 1 ? next.length + pend.length + phoneN + '번째 영상을 첨부했습니다' : '영상 ' + added + '개를 첨부했습니다')
    setFiles(next)
  }
  const dragProps = (k: 'drop' | 'slot') => ({
    onDragOver: (e: DragEvent) => {
      e.preventDefault()
      if (!over[k]) setOver({ ...over, [k]: true })
    },
    onDragLeave: () => setOver({ ...over, [k]: false }),
    onDrop: (e: DragEvent) => {
      e.preventDefault()
      setOver({ ...over, [k]: false })
      if (e.dataTransfer.files.length) add(e.dataTransfer.files)
    },
  })
  const onBefore = (fd: FormData) => {
    if (!n) {
      window.ppToast('보행 영상을 1개 이상 올려 주세요')
      return false
    }
    // 아직 올리는 중이면 제출을 미루고 진행을 보여 준다. 다 올라가면 위 효과가 다시 제출한다
    if (pre && (files.length || upFile)) {
      setAutoStart({ total: sent.length + files.length, fails: fails.current })
      return false
    }
    fd.delete('files')
    if (!pre) files.forEach((f) => fd.append('files', f))
    fd.set('demo_count', String(locals.length || phoneN ? 0 : demo))
    fd.set('sid', phoneSid)
    fd.set('sid_new', phoneCreated ? '1' : '')
    leave.current.submitted = true
  }

  // 반려견을 바꾸면 다른 반려견의 QR 회차는 놓는다(그 회차로 영상이 올라가지 않게). 이미 올라온 영상이 있으면 확인을 받는다
  const pickDog = (id: string) => {
    if (id === sel.id) return
    if (phoneSid && pre && phoneCreated && !foreignN) {
      // 이 화면에서 올린 영상뿐이면 그 회차를 지우고, 고른 영상을 바꾼 반려견의 회차로 다시 올린다
      gen.current++
      dropEmptySession(phoneSid)
      setFiles([...sent.map((s) => s.file), ...files])
      setSent([])
      setPhoneSid('')
      setPhoneCreated(false)
      setShowQr(false)
    } else if (phoneSid) {
      const to = dogOf(acct, id)?.name ?? '다른 반려견'
      if (phoneN && !window.confirm(`올린 영상 ${phoneN}개는 ${sel.name}의 회차에 그대로 남습니다. ${to}(으)로 바꾸시겠습니까?`)) return
      if (!phoneN && phoneCreated) dropEmptySession(phoneSid)
      gen.current++
      setSent([])
      setPhoneSid('')
      setPhoneCreated(false)
      setShowQr(false)
    }
    setSelId(id)
  }

  // 이 회차 취소: 회차와 올라온 영상이 모두 지워진다(되돌릴 수 없음). 영상이 있으면 개수를 알려 확인을 받는다
  const cancelPhone = async () => {
    if (phoneN && !window.confirm(`이 회차에 올라온 영상 ${phoneN}개${phoneCreated ? '' : '(앞서 올린 영상 포함)'}가 모두 지워집니다. 회차를 취소하시겠습니까?`)) return
    if (await cancelPhoneSession(phoneSid)) {
      gen.current++
      setFiles([])
      setSent([])
      setPhoneSid('')
      setPhoneCreated(false)
      setShowQr(false)
    }
  }

  const startPhone = async () => {
    // 시연 기관은 서버에 회차가 없어 QR 로 폰과 이을 수 없다(서버에 보내면 401)
    if (!acct || !isRemote(acct.id)) return window.ppToast('체험 모드에서는 폰으로 촬영하기를 쓸 수 없습니다. 로그인하면 쓸 수 있습니다')
    try {
      const weight = (document.querySelector('input[name=weight]') as HTMLInputElement | null)?.value ?? ''
      const o = phoneSid ? { id: phoneSid, created: phoneCreated } : await openSession(sel.id, weight)
      setPhoneSid(o.id)
      setPhoneCreated(o.created)
      setShowQr(true)
    } catch (e) {
      window.ppToast(e instanceof Error ? e.message : '회차를 열지 못했습니다')
    }
  }

  return (
    <Base acct={acct} me={me} nav="upload" toast={toast} modals={<><PetModal next_url="/upload" /><GuideModal /></>}>
      <main style={css('max-width:none;margin:0;padding:32px 80px 96px;display:flex;flex-direction:column;gap:24px')}>
        <div style={css('display:flex;flex-direction:column;gap:6px')}><h1 style={css('margin:0;font-size:28px;font-weight:800;letter-spacing:-0.9px')}>보행 영상 분석</h1></div>
        <PostForm id="upForm" action="/analyze" encType="multipart/form-data" onBefore={onBefore} style={css('display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start;margin:0')}>
          <input type="hidden" name="dog" value={sel.id} />
          <input type="hidden" name="demo_count" value="0" />
          <input type="hidden" name="sid" value={phoneSid} />
          <input type="hidden" name="sid_new" value={phoneCreated ? '1' : ''} />
          <input type="file" id="fileInput" ref={picker} accept="video/*,.mp4,.mov,.m4v" multiple hidden
            onChange={(e) => {
              if (e.currentTarget.files) add(e.currentTarget.files)
              e.currentTarget.value = ''
            }} />
          <input type="file" name="files" id="filesField" multiple hidden />
          <div style={css('flex:1 1 460px;min-width:0;max-width:1100px;display:flex;flex-direction:column;gap:22px')}>
            <div style={css('display:flex;flex-direction:column;gap:10px')}><b style={css('font-size:15px')}>1. 반려견 선택</b>
              <input id="dogFilter" placeholder="이름, 동물번호로 찾기" autoComplete="off" onInput={(e) => setFilt(e.currentTarget.value.trim())} style={css('height:44px;max-width:420px;border-radius:12px;border:1px solid #E2DCD3;background:#fff;padding:0 14px;font-size:15px;outline:none')} />
              <div style={css('max-height:264px;overflow-y:auto;border:1px solid #ECE8E2;border-radius:14px;background:#fff')}>
                {dogs.map((d, i) => (
                  // 환자가 많아서 이름·동물번호로 걸러 본다
                  <div key={d.id} className="up-dog hv-row" data-id={d.id} data-kg={d.kg} data-name={d.name} data-key={`${d.name} ${d.no}`} onClick={() => pickDog(d.id)}
                    style={css(`display:${!filt || `${d.name} ${d.no}`.indexOf(filt) >= 0 ? 'flex' : 'none'};align-items:center;gap:12px;padding:9px 14px;border-top:${i ? '1px solid #F2EFEA' : 'none'};cursor:pointer`)}>
                    <div className="av" style={css(`width:34px;height:34px;flex:none;border-radius:50%;background:${d.av};color:${d.avc};display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;box-shadow:${d.ring}`)}>{d.init}</div>
                    <span className="nm" style={css(`font-size:15px;color:${d.nc};font-weight:${d.nw}`)}>{d.name}</span>
                    <span style={css('font-size:13px;color:#5B6472')}>{[d.no, d.breed].filter(Boolean).join(', ')}{d.kg ? `, ${d.kg}kg` : ''}</span>
                  </div>
                ))}
              </div>
              <span data-pet="new" style={css('align-self:flex-start;font-size:15px;font-weight:700;color:#D2601A;cursor:pointer')}>+ 새 반려견 등록</span>
            </div>
            <label style={css('display:flex;flex-direction:column;gap:8px;max-width:320px')}><span style={css('font-size:15px;font-weight:700')}>2. 오늘 체중 <span style={css('color:#5B6472;font-weight:500;font-size:14px')}>선택</span></span><div style={css('position:relative;display:flex')}><input className="inp" name="weight" id="sessW" readOnly={!!phoneSid} title={phoneSid ? '영상을 올리기 시작한 뒤에는 체중을 바꿀 수 없습니다' : undefined} placeholder={sel.kg ? '등록 체중 ' + sel.kg : '예) 28.1'} inputMode="decimal" style={css('flex:1;min-width:0;height:52px;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 44px 0 16px;font-size:15px;color:#1B2433;outline:none')} /><span style={css('position:absolute;right:16px;top:0;bottom:0;display:flex;align-items:center;font-size:15px;color:#5B6472;pointer-events:none')}>kg</span></div>{phoneSid ? <span style={css('font-size:13px;color:#5B6472;line-height:1.5')}>영상을 올리기 시작해 체중이 고정됐습니다. 바꾸려면 영상을 모두 지운 뒤 다시 넣어 주세요</span> : null}</label>
            <div style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:15px;font-weight:700')}>오늘 바이탈 <span style={css('color:#5B6472;font-weight:500;font-size:14px')}>선택</span></span>
              <div style={css('display:grid;grid-template-columns:repeat(4,minmax(0,140px));gap:10px')}>
                {VITALS.map(([nm, label, ph]) => (
                  <label key={nm} style={css('display:flex;flex-direction:column;gap:4px;min-width:0')}><span style={css('font-size:13px;color:#5B6472')}>{label}</span><input className="inp" name={nm} inputMode="decimal" placeholder={ph} style={css('height:48px;width:100%;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 12px;font-size:15px;outline:none')} /></label>
                ))}
              </div>
            </div>
            <label style={css('display:flex;flex-direction:column;gap:8px;max-width:320px')}><span style={css('font-size:15px;font-weight:700')}>측정한 사람</span><input className="inp author-inp" name="author" placeholder="예) 박민준 테크니션" style={css('height:48px;width:100%;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 12px;font-size:15px;outline:none')} /></label>
            <div style={css('display:flex;flex-direction:column;gap:12px')}>
              <div style={css('display:flex;align-items:baseline;justify-content:space-between;gap:12px')}><b style={css('font-size:15px')}>3. 영상 올리기</b><span id="shotN" style={css('font-size:15px;font-weight:700;color:#B4501A;font-variant-numeric:tabular-nums')}>{n + ' / ' + max}</span></div>
              {!MOCK ? (
                <div style={css('display:flex;align-items:center;gap:10px;flex-wrap:wrap')}>
                  <button type="button" className="bt hv-border" onClick={startPhone} style={css('height:44px;padding:0 16px;border-radius:12px;background:#fff;border:1px solid #E2DCD3;display:flex;align-items:center;gap:8px;font-size:15px;font-weight:700')}>📱 폰으로 촬영하기</button>
                  {phoneSid ? <button type="button" className="hv-dark" onClick={cancelPhone} style={css('height:44px;padding:0 10px;background:none;border:0;font-size:14px;font-weight:600;color:#5B6472;text-decoration:underline;cursor:pointer')}>이 회차 취소</button> : null}
                  <span style={css('font-size:13px;color:#5B6472')}>{foreignN ? `폰에서 영상 ${foreignN}개가 올라왔습니다` : phoneSid && !sent.length && !files.length ? 'QR 을 찍어 폰에서 촬영해 주세요' : 'QR 을 폰으로 찍으면 폰 카메라로 바로 찍어 이 회차에 올릴 수 있습니다'}</span>
                </div>
              ) : null}
              <div id="dropZone" className="drop" onClick={() => picker.current?.click()} {...dragProps('drop')}
                style={css(`aspect-ratio:16 / 7;border-radius:18px;border:2px dashed ${over.drop ? '#D2601A' : '#D9D2C7'};background:${over.drop ? '#FFF6EE' : '#fff'};display:${n ? 'none' : 'flex'};flex-direction:column;align-items:center;justify-content:center;gap:12px;cursor:pointer;text-align:center;padding:24px`)}>
                <div style={css('width:56px;height:56px;border-radius:16px;background:#FCEEE3;color:#D2601A;display:flex;align-items:center;justify-content:center')}><svg width="28" height="28" viewBox="0 0 24 24"><use href="#w-up"></use></svg></div>
                <b style={css('font-size:18px')}>영상을 끌어다 놓거나 눌러서 선택하세요</b>
                <span style={css('font-size:14px;color:#5B6472')}>MP4/MOV, 가로 영상, 4초씩 16개까지 차례대로</span>
              </div>
              <div id="fileArea" style={css(`display:${n ? 'grid' : 'none'};grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;align-items:start`)}>
                <div style={css('border-radius:18px;overflow:hidden;background:#141B22;position:relative;aspect-ratio:16 / 9')}>
                  <video id="preview" ref={video} src={preview} autoPlay muted loop playsInline style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')}></video>
                  <div style={css('position:absolute;left:14px;right:14px;bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:10px')}>
                    <span style={css('height:34px;padding:0 12px;border-radius:17px;background:rgba(14,18,23,.72);color:#fff;display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;font-variant-numeric:tabular-nums')}><svg width="16" height="16" viewBox="0 0 24 24" style={css('color:#3DD68C')}><use href="#w-check"></use></svg><span id="fileName">{(sel ? sel.name : '반려견') + ', 영상 ' + n}</span></span>
                    <span id="clearFiles" onClick={() => { if (pre && phoneSid) void cancelPhone(); else { setFiles([]); setDemo(0) } }} style={css('height:34px;padding:0 12px;border-radius:17px;background:rgba(255,255,255,.92);display:flex;align-items:center;font-size:13px;font-weight:700;cursor:pointer')}>모두 지우기</span>
                  </div>
                </div>
                <div className="drop" id="slotBox" {...dragProps('slot')} style={css(`background:${over.slot ? '#FFF6EE' : '#fff'};border:1px solid ${over.slot ? '#D2601A' : '#ECE8E2'};border-radius:18px;padding:18px;display:flex;flex-direction:column;gap:12px`)}>
                  <div style={css('height:6px;border-radius:3px;background:#FCEEE3')}><div id="shotBar" style={css(`width:${Math.round((n / max) * 100)}%;height:100%;border-radius:3px;background:#D2601A;transition:width .3s`)}></div></div>
                  <div id="slots" style={css('display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px')}>
                    {/* 칸 16개 */}
                    {Array.from({ length: max }, (_, i) => {
                      const done = i < n
                      const next = i === n
                      const fromPhone = i < phoneN // 폰에서 올라온 영상(이 브라우저에 파일이 없다)
                      const ps = fromPhone ? phoneShots[i] : undefined
                      // 서버에 올라간 칸이라도 이 화면에서 올린 영상이면 들고 있는 파일로 썸네일을 그린다
                      const own = ps ? mine.get(ps.id) : undefined
                      const file = fromPhone ? own : locals[i - phoneN]
                      const failed = ps?.status === 'FAILED'
                      return (
                        <div key={i} title={file ? file.name : ps ? (failed ? `분석 실패: ${ps.fail_reason?.message ?? ''}` : '폰에서 올린 영상') : undefined} onClick={next ? () => picker.current?.click() : undefined}
                          style={css('aspect-ratio:16 / 10;border-radius:10px;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;' +
                            'background:' + (failed ? '#7A2E22' : done ? '#141B22' : next ? '#FCEEE3' : '#F4F1EC') + ';border:1.5px ' + (next ? 'dashed' : 'solid') + ' ' + (done ? '#141B22' : next ? '#D2601A' : '#ECE8E2') + ';cursor:' + (next ? 'pointer' : 'default'))}>
                          {file && thumbs.get(file) ? <img src={thumbs.get(file)} alt="" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')} /> : null}
                          {ps && !own && phoneVideos[ps.id] ? <video src={`${phoneVideos[ps.id]}#t=0.1`} muted playsInline preload="metadata" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')} /> : null}
                          {fromPhone && (failed || !own) ? <span style={css('position:relative;font-size:12px;font-weight:700;color:rgba(255,255,255,.85);text-shadow:0 1px 3px rgba(0,0,0,.6)')}>{failed ? '분석 실패' : phoneCreated ? '폰' : '올린 영상'}</span> : null}
                          {ps && failed ? <button type="button" title="다시 분석" onClick={() => void shotAction('retry', ps.id, reloadPhone)} style={css('position:absolute;left:6px;bottom:5px;height:22px;padding:0 8px;border-radius:11px;border:0;background:rgba(255,255,255,.92);font-size:12px;font-weight:700;cursor:pointer')}>다시 분석</button> : null}
                          {next ? <span style={css('font-size:22px;font-weight:500;color:#D2601A;line-height:1')}>+</span> : null}
                          <span style={css('position:absolute;left:7px;top:4px;font-size:12px;font-weight:700;font-variant-numeric:tabular-nums;text-shadow:' + (done ? '0 1px 3px rgba(0,0,0,.6)' : 'none') + ';color:' + (done ? 'rgba(255,255,255,.85)' : next ? '#B4501A' : '#A0A7B2'))}>{i + 1}</span>
                        </div>
                      )
                    })}
                  </div>
                  <span id="shotHint" style={css('font-size:13px;color:#5B6472;line-height:1.5')}>{n >= max ? '16개를 모두 첨부했습니다. 분석을 시작해 주세요.' : n + 1 + '번째 영상을 이어서 올려 주세요. 16개를 모두 채우면 결과가 더 정확합니다.'}</span>
                </div>
              </div>
            </div>
            <div data-open="guideModal" className="hv-dark" style={css('align-self:flex-start;display:flex;align-items:center;gap:8px;margin-top:-6px;cursor:pointer;color:#5B6472;font-size:15px;font-weight:600')}><span style={css('width:20px;height:20px;border-radius:50%;border:1.6px solid currentColor;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;font-family:Georgia,serif;font-style:italic;flex:none')}>i</span>영상 촬영은 어떻게 하나요?</div>
            <button className="bt" type="submit" id="startBtn" style={css(`align-self:flex-end;width:240px;height:58px;border-radius:14px;background:${n ? '#D2601A' : '#C3C8CF'};color:#fff;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700`)}>분석 시작</button>
          </div>
        </PostForm>
        {/* 영상을 다 올려야 분석 중 화면으로 넘어간다. 그동안 멈춘 것처럼 보이지 않게 몇 개째인지 덮개로 알린다 */}
        {wait ? (
          <div role="status" aria-live="polite" style={css('position:fixed;inset:0;z-index:1000;background:rgba(250,249,245,.94);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px;text-align:center')}>
            <b style={css('font-size:24px;letter-spacing:-0.6px;font-variant-numeric:tabular-nums')}>{wait.total ? `영상 올리는 중 ${wait.done} / ${wait.total}` : '분석을 준비하는 중입니다'}</b>
            {wait.total ? <div style={css('width:320px;max-width:100%;height:8px;border-radius:4px;background:#FCEEE3')}><div style={css(`width:${Math.round((wait.done / wait.total) * 100)}%;height:100%;border-radius:4px;background:#D2601A;transition:width .3s`)}></div></div> : null}
            <span style={css('font-size:15px;color:#5B6472')}>다 올리면 분석 화면으로 넘어갑니다. 이 창을 닫지 말아 주세요</span>
          </div>
        ) : null}
        {showQr && phoneSid ? <PhoneCaptureModal sid={phoneSid} shots={foreignN} onClose={() => setShowQr(false)} /> : null}
      </main>
    </Base>
  )
}
