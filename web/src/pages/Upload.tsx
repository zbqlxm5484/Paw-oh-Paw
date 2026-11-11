// upload.html + static/upload.js + main.py upload(): 반려견 고르기, 영상 16개까지 차례로 첨부(끌어 놓기 · 고르기), 분석 시작
import { useFirstFrames, useShotVideos } from '../app/thumbs'
import { useEffect, useRef, useState, type DragEvent } from 'react'
import { cancelPhoneSession, dropEmptySession, openSession, PhoneCaptureModal, shotAction, usePhoneShots } from './parts/PhoneCapture'
import { MOCK, isRemote } from '../store/backend'
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
  useTitle('보행 영상 분석 · Paw oh Paw')
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
  // 이번 화면에서 새로 연 회차인지(이어 쓰는 회차면 원래 있던 영상도 센다), 분석을 시작했는지
  const [phoneCreated, setPhoneCreated] = useState(false)
  const leave = useRef({ sid: '', created: false, n: 0, submitted: false })
  leave.current = { ...leave.current, sid: phoneSid, created: phoneCreated, n: phoneN }
  // 영상 없이 화면을 떠나면 새로 연 빈 회차를 지운다
  useEffect(() => () => {
    const l = leave.current
    if (l.sid && l.created && !l.n && !l.submitted) dropEmptySession(l.sid)
  }, [])
  const [over, setOver] = useState({ drop: false, slot: false })
  const picker = useRef<HTMLInputElement>(null)
  const video = useRef<HTMLVideoElement>(null)
  const urls = useRef(new WeakMap<File, string>())
  const thumbs = useFirstFrames(files)
  const phoneVideos = useShotVideos(phoneShots)
  // 폰에서 16개가 다 올라오면 QR 창을 닫는다(폰도 촬영 화면을 닫는다)
  useEffect(() => {
    if (phoneN >= MAX_SHOTS && showQr) {
      setShowQr(false)
      window.ppToast(`폰에서 영상 ${MAX_SHOTS}개가 모두 올라왔습니다`)
    }
  }, [phoneN, showQr])

  const go: Go | null = acct && !acct.dogs.length ? redirect('/home?modal=pet', '먼저 반려견을 등록해 주세요') : null
  useRedirect(go)

  // 첫 영상을 미리 보기(없으면 견본 영상)
  const want = files.length ? files[0] : null
  let preview = SAMPLE
  if (want) {
    let u = urls.current.get(want)
    if (!u) {
      u = URL.createObjectURL(want)
      urls.current.set(want, u)
    }
    preview = u
  }
  useEffect(() => {
    const v = video.current
    if (v) v.muted = true
  })

  if (!acct || go || !first) return null
  const sel = dogOf(acct, selId) || first
  const order = [first, ...acct.dogs.filter((d) => d.id !== first.id)] // 고른 반려견을 맨 위에
  const dogs = order.map((d) => ({ id: d.id, init: d.name.slice(0, 1), name: d.name, no: d.no, breed: d.breed || '견종 미입력', kg: d.kg, ...avatar(d.id === sel.id) }))
  const n = files.length + phoneN || demo
  const max = MAX_SHOTS

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
      if (next.length + phoneN < max) { // 폰에서 올라온 영상까지 합쳐 16개
        next.push(f)
        added++
      }
    })
    if (added) setDemo(0)
    if (bad && !added) return window.ppToast('영상 파일(MP4 · MOV)만 올릴 수 있습니다')
    if (added) window.ppToast(added === 1 ? next.length + '번째 영상을 첨부했습니다' : '영상 ' + added + '개를 첨부했습니다')
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
    fd.delete('files')
    files.forEach((f) => fd.append('files', f))
    fd.set('demo_count', String(files.length || phoneN ? 0 : demo))
    fd.set('sid', phoneSid)
    leave.current.submitted = true
  }

  // 반려견을 바꾸면 다른 반려견의 QR 회차는 놓는다(그 회차로 영상이 올라가지 않게). 이미 올라온 영상이 있으면 확인을 받는다
  const pickDog = (id: string) => {
    if (id === sel.id) return
    if (phoneSid) {
      const to = dogOf(acct, id)?.name ?? '다른 반려견'
      if (phoneN && !window.confirm(`폰으로 올린 영상 ${phoneN}개는 ${sel.name}의 회차에 그대로 남습니다. ${to}(으)로 바꾸시겠습니까?`)) return
      if (!phoneN && phoneCreated) dropEmptySession(phoneSid)
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
        <div style={css('display:flex;flex-direction:column;gap:6px')}><h1 style={css('margin:0;font-size:34px;font-weight:800;letter-spacing:-0.9px')}>보행 영상 분석</h1></div>
        <PostForm id="upForm" action="/analyze" encType="multipart/form-data" onBefore={onBefore} style={css('display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start;margin:0')}>
          <input type="hidden" name="dog" value={sel.id} />
          <input type="hidden" name="demo_count" value="0" />
          <input type="hidden" name="sid" value={phoneSid} />
          <input type="file" id="fileInput" ref={picker} accept="video/*,.mp4,.mov,.m4v" multiple hidden
            onChange={(e) => {
              if (e.currentTarget.files) add(e.currentTarget.files)
              e.currentTarget.value = ''
            }} />
          <input type="file" name="files" id="filesField" multiple hidden />
          <div style={css('flex:1 1 460px;min-width:0;max-width:1100px;display:flex;flex-direction:column;gap:22px')}>
            <div style={css('display:flex;flex-direction:column;gap:10px')}><b style={css('font-size:16px')}>1. 반려견 선택</b>
              <input id="dogFilter" placeholder="이름 · 동물번호로 찾기" autoComplete="off" onInput={(e) => setFilt(e.currentTarget.value.trim())} style={css('height:44px;max-width:420px;border-radius:12px;border:1px solid #E2DCD3;background:#fff;padding:0 14px;font-size:15px;outline:none')} />
              <div style={css('max-height:264px;overflow-y:auto;border:1px solid #ECE8E2;border-radius:14px;background:#fff')}>
                {dogs.map((d, i) => (
                  // 환자가 많아서 이름·동물번호로 걸러 본다
                  <div key={d.id} className="up-dog hv-row" data-id={d.id} data-kg={d.kg} data-name={d.name} data-key={`${d.name} ${d.no}`} onClick={() => pickDog(d.id)}
                    style={css(`display:${!filt || `${d.name} ${d.no}`.indexOf(filt) >= 0 ? 'flex' : 'none'};align-items:center;gap:12px;padding:9px 14px;border-top:${i ? '1px solid #F2EFEA' : 'none'};cursor:pointer`)}>
                    <div className="av" style={css(`width:34px;height:34px;flex:none;border-radius:50%;background:${d.av};color:${d.avc};display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;box-shadow:${d.ring}`)}>{d.init}</div>
                    <span className="nm" style={css(`font-size:15px;color:${d.nc};font-weight:${d.nw}`)}>{d.name}</span>
                    <span style={css('font-size:13px;color:#7A808A')}>{[d.no, d.breed].filter(Boolean).join(' · ')}{d.kg ? ` · ${d.kg}kg` : ''}</span>
                  </div>
                ))}
              </div>
              <span data-pet="new" style={css('align-self:flex-start;font-size:14.5px;font-weight:700;color:#D2601A;cursor:pointer')}>+ 새 반려견 등록</span>
            </div>
            <label style={css('display:flex;flex-direction:column;gap:8px;max-width:320px')}><span style={css('font-size:16px;font-weight:700')}>2. 오늘 체중 <span style={css('color:#A0A7B2;font-weight:500;font-size:14px')}>선택</span></span><div style={css('position:relative;display:flex')}><input className="inp" name="weight" id="sessW" readOnly={!!phoneSid} title={phoneSid ? '폰 촬영 회차를 연 뒤에는 체중을 바꿀 수 없습니다' : undefined} placeholder={sel.kg ? '등록 체중 ' + sel.kg : '예) 28.1'} inputMode="decimal" style={css('flex:1;min-width:0;height:52px;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 44px 0 16px;font-size:16px;color:#1B2433;outline:none')} /><span style={css('position:absolute;right:16px;top:0;bottom:0;display:flex;align-items:center;font-size:15px;color:#5B6472;pointer-events:none')}>kg</span></div></label>
            <div style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:16px;font-weight:700')}>오늘 바이탈 <span style={css('color:#A0A7B2;font-weight:500;font-size:14px')}>선택</span></span>
              <div style={css('display:grid;grid-template-columns:repeat(4,minmax(0,140px));gap:10px')}>
                {VITALS.map(([nm, label, ph]) => (
                  <label key={nm} style={css('display:flex;flex-direction:column;gap:4px;min-width:0')}><span style={css('font-size:12.5px;color:#5B6472')}>{label}</span><input className="inp" name={nm} inputMode="decimal" placeholder={ph} style={css('height:48px;width:100%;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 12px;font-size:15px;outline:none')} /></label>
                ))}
              </div>
            </div>
            <label style={css('display:flex;flex-direction:column;gap:8px;max-width:320px')}><span style={css('font-size:16px;font-weight:700')}>측정한 사람</span><input className="inp author-inp" name="author" placeholder="예) 박민준 테크니션" style={css('height:48px;width:100%;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 12px;font-size:15px;outline:none')} /></label>
            <div style={css('display:flex;flex-direction:column;gap:12px')}>
              <div style={css('display:flex;align-items:baseline;justify-content:space-between;gap:12px')}><b style={css('font-size:16px')}>3. 영상 올리기</b><span id="shotN" style={css('font-size:15px;font-weight:700;color:#B4501A;font-variant-numeric:tabular-nums')}>{n + ' / ' + max}</span></div>
              {!MOCK ? (
                <div style={css('display:flex;align-items:center;gap:10px;flex-wrap:wrap')}>
                  <button type="button" className="bt hv-border" onClick={startPhone} style={css('height:42px;padding:0 16px;border-radius:12px;background:#fff;border:1px solid #E2DCD3;display:flex;align-items:center;gap:8px;font-size:14.5px;font-weight:700')}>📱 폰으로 촬영하기</button>
                  {phoneSid ? <button type="button" className="hv-dark" onClick={cancelPhone} style={css('height:42px;padding:0 10px;background:none;border:0;font-size:13.5px;font-weight:600;color:#8E949C;text-decoration:underline;cursor:pointer')}>이 회차 취소</button> : null}
                  <span style={css('font-size:13px;color:#5B6472')}>{phoneSid ? (phoneN ? `폰에서 영상 ${phoneN}개가 올라왔습니다` : 'QR 을 찍어 폰에서 촬영해 주세요') : 'QR 을 폰으로 찍으면 폰 카메라로 바로 찍어 이 회차에 올릴 수 있습니다'}</span>
                </div>
              ) : null}
              <div id="dropZone" className="drop" onClick={() => picker.current?.click()} {...dragProps('drop')}
                style={css(`aspect-ratio:16 / 7;border-radius:18px;border:2px dashed ${over.drop ? '#D2601A' : '#D9D2C7'};background:${over.drop ? '#FFF6EE' : '#fff'};display:${n ? 'none' : 'flex'};flex-direction:column;align-items:center;justify-content:center;gap:12px;cursor:pointer;text-align:center;padding:24px`)}>
                <div style={css('width:56px;height:56px;border-radius:16px;background:#FCEEE3;color:#D2601A;display:flex;align-items:center;justify-content:center')}><svg width="28" height="28" viewBox="0 0 24 24"><use href="#w-up"></use></svg></div>
                <b style={css('font-size:17px')}>영상을 끌어다 놓거나 눌러서 선택하세요</b>
                <span style={css('font-size:14px;color:#5B6472')}>MP4 · MOV · 가로 영상 · 4초씩 16개까지 차례대로</span>
              </div>
              <div id="fileArea" style={css(`display:${n ? 'grid' : 'none'};grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;align-items:start`)}>
                <div style={css('border-radius:18px;overflow:hidden;background:#141B22;position:relative;aspect-ratio:16 / 9')}>
                  <video id="preview" ref={video} src={preview} autoPlay muted loop playsInline style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')}></video>
                  <div style={css('position:absolute;left:14px;right:14px;bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:10px')}>
                    <span style={css('height:34px;padding:0 12px;border-radius:17px;background:rgba(14,18,23,.72);color:#fff;display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;font-variant-numeric:tabular-nums')}><svg width="16" height="16" viewBox="0 0 24 24" style={css('color:#3DD68C')}><use href="#w-check"></use></svg><span id="fileName">{(sel ? sel.name : '반려견') + ' · 영상 ' + n}</span></span>
                    <span id="clearFiles" onClick={() => { setFiles([]); setDemo(0) }} style={css('height:34px;padding:0 12px;border-radius:17px;background:rgba(255,255,255,.92);display:flex;align-items:center;font-size:13px;font-weight:700;cursor:pointer')}>모두 지우기</span>
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
                      const file = fromPhone ? undefined : files[i - phoneN]
                      const ps = fromPhone ? phoneShots[i] : undefined
                      const busy = !!ps && (ps.status === 'SUBMITTED' || ps.status === 'ANALYZING')
                      const failed = ps?.status === 'FAILED'
                      return (
                        <div key={i} title={done && file ? file.name : ps ? (failed ? `분석 실패: ${ps.fail_reason?.message ?? ''}` : '폰에서 올린 영상') : undefined} onClick={next ? () => picker.current?.click() : undefined}
                          style={css('aspect-ratio:16 / 10;border-radius:10px;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;' +
                            'background:' + (failed ? '#7A2E22' : done ? '#141B22' : next ? '#FCEEE3' : '#F4F1EC') + ';border:1.5px ' + (next ? 'dashed' : 'solid') + ' ' + (done ? '#141B22' : next ? '#D2601A' : '#ECE8E2') + ';cursor:' + (next ? 'pointer' : 'default'))}>
                          {file && thumbs.get(file) ? <img src={thumbs.get(file)} alt="" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')} /> : null}
                          {ps && phoneVideos[ps.id] ? <video src={`${phoneVideos[ps.id]}#t=0.1`} muted playsInline preload="metadata" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')} /> : null}
                          {fromPhone ? <span style={css('font-size:12px;font-weight:700;color:rgba(255,255,255,.85)')}>{failed ? '분석 실패' : busy ? '분석 중' : phoneCreated ? '폰' : '올린 영상'}</span> : null}
                          {ps && failed ? <button type="button" title="다시 분석" onClick={() => void shotAction('retry', ps.id, reloadPhone)} style={css('position:absolute;left:6px;bottom:5px;height:22px;padding:0 8px;border-radius:11px;border:0;background:rgba(255,255,255,.92);font-size:11px;font-weight:700;cursor:pointer')}>다시 분석</button> : null}
                          {ps && !busy ? <button type="button" title="이 영상 지우기" aria-label="이 영상 지우기" onClick={() => { if (window.confirm(`${i + 1}번 영상을 지우시겠습니까? 지운 영상은 되돌릴 수 없습니다.`)) void shotAction('delete', ps.id, reloadPhone) }} style={css('position:absolute;right:5px;top:4px;width:22px;height:22px;border-radius:11px;border:0;background:rgba(255,255,255,.85);color:#1B2433;font-size:13px;line-height:1;cursor:pointer')}>×</button> : null}
                          {next ? <span style={css('font-size:22px;font-weight:500;color:#D2601A;line-height:1')}>+</span> : null}
                          <span style={css('position:absolute;left:7px;top:4px;font-size:11px;font-weight:700;font-variant-numeric:tabular-nums;text-shadow:' + (done ? '0 1px 3px rgba(0,0,0,.6)' : 'none') + ';color:' + (done ? 'rgba(255,255,255,.85)' : next ? '#B4501A' : '#A0A7B2'))}>{i + 1}</span>
                        </div>
                      )
                    })}
                  </div>
                  <span id="shotHint" style={css('font-size:13px;color:#5B6472;line-height:1.5')}>{n >= max ? '16개를 모두 첨부했습니다. 분석을 시작해 주세요.' : n + 1 + '번째 영상을 이어서 올려 주세요. 16개를 모두 채우면 결과가 더 정확합니다.'}</span>
                </div>
              </div>
            </div>
            <div data-open="guideModal" className="hv-dark" style={css('align-self:flex-start;display:flex;align-items:center;gap:8px;margin-top:-6px;cursor:pointer;color:#5B6472;font-size:14.5px;font-weight:600')}><span style={css('width:20px;height:20px;border-radius:50%;border:1.6px solid currentColor;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;font-family:Georgia,serif;font-style:italic;flex:none')}>i</span>영상 촬영은 어떻게 하나요?</div>
            <button className="bt" type="submit" id="startBtn" style={css(`align-self:flex-end;width:240px;height:58px;border-radius:14px;background:${n ? '#D2601A' : '#C3C8CF'};color:#fff;display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:700`)}>분석 시작</button>
          </div>
        </PostForm>
        {showQr && phoneSid ? <PhoneCaptureModal sid={phoneSid} shots={phoneN} onClose={() => setShowQr(false)} /> : null}
      </main>
    </Base>
  )
}
