// 폰으로 촬영(웹 업로드 화면): 회차를 먼저 열고 QR 을 띄운다. 폰으로 QR 을 찍으면 앱 화면(같은 도메인 /)의
// 그 회차 촬영 화면이 열리고, 같은 계정으로 로그인해 찍은 영상이 이 회차로 올라온다. 웹은 몇 초마다 회차를 읽어 올라온 수를 보인다.
// 1단계는 같은 계정 로그인 방식. 반응이 좋으면 로그인 없는 촬영 전용 링크(백엔드 토큰)로 넓힌다.
import { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import { api, ApiError, type ShotOut } from '../../api/client'
import { css } from '../../app/css'

const POLL_MS = 3000

/** 앱(폰 화면)의 주소. 배포에서는 웹(/web/)과 같은 도메인의 / 이다. 로컬 개발은 VITE_APP_URL 로 */
export function appRecordUrl(sid: string): string {
  const base = (import.meta.env.VITE_APP_URL as string | undefined) || window.location.origin
  return `${base.replace(/\/$/, '')}/sessions/${sid}/record`
}

/** 이 반려견의 회차를 연다. 이미 측정 중인 회차가 있으면 그 회차를 쓴다 */
export async function openSession(dog: string, weight: string): Promise<string> {
  try {
    return (await api.startSession(dog, weight.trim() ? { weight_kg: Number(weight) } : {})).id
  } catch (e) {
    const open = e instanceof ApiError && e.code === 'SESSION_ALREADY_OPEN' ? (await api.dog(dog).catch(() => null))?.open_session_id : null
    if (open) return open
    throw e
  }
}

/** 회차에 올라온 촬영(올린 순서)을 몇 초마다 읽는다. reload 는 지우기·다시 분석 뒤 바로 다시 읽을 때 */
export function usePhoneShots(sid: string): { shots: ShotOut[]; reload: () => void } {
  const [shots, setShots] = useState<ShotOut[]>([])
  const [k, setK] = useState(0)
  useEffect(() => {
    if (!sid) {
      setShots([])
      return
    }
    let alive = true
    let t = 0
    const tick = async () => {
      try {
        const s = await api.session(sid)
        if (alive) setShots([...s.shots].sort((a, b) => a.seq_no - b.seq_no))
      } catch {
        /* 다음에 다시 */
      }
      if (alive) t = window.setTimeout(tick, POLL_MS)
    }
    void tick()
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [sid, k])
  return { shots, reload: () => setK((x) => x + 1) }
}

/** 폰에서 올린 촬영 하나를 지운다 / 실패한 촬영을 다시 분석한다. 실패하면 서버 문구를 띄운다 */
export async function shotAction(kind: 'delete' | 'retry', id: string, done: () => void): Promise<void> {
  try {
    if (kind === 'delete') await api.deleteShot(id)
    else await api.retryShot(id)
    window.ppToast(kind === 'delete' ? '영상을 지웠어요' : '다시 분석을 시작했어요')
  } catch (e) {
    window.ppToast(e instanceof ApiError ? e.message : kind === 'delete' ? '영상을 지우지 못했어요' : '다시 분석하지 못했어요')
  }
  done()
}

/** 폰 촬영으로 연 회차를 취소한다(아직 분석 전). 올라온 영상도 같이 지워진다 */
export async function cancelPhoneSession(sid: string): Promise<boolean> {
  try {
    await api.cancelSession(sid)
    window.ppToast('이 회차를 취소했어요')
    return true
  } catch (e) {
    window.ppToast(e instanceof ApiError ? e.message : '회차를 취소하지 못했어요')
    return false
  }
}

export function PhoneCaptureModal({ sid, shots, onClose }: { sid: string; shots: number; onClose: () => void }) {
  const url = appRecordUrl(sid)
  const [qr, setQr] = useState('')
  useEffect(() => {
    void QRCode.toDataURL(url, { margin: 1, width: 240, color: { dark: '#1B2433', light: '#FFFFFF' } }).then(setQr)
  }, [url])
  return (
    <div className="no-print" onClick={onClose} style={css('position:fixed;inset:0;background:rgba(14,18,23,.55);z-index:70;display:flex;align-items:center;justify-content:center;padding:24px')}>
      <div onClick={(e) => e.stopPropagation()} style={css('width:420px;max-width:100%;background:#fff;border-radius:18px;padding:28px;display:flex;flex-direction:column;align-items:center;gap:14px;text-align:center')}>
        <b style={css('font-size:20px')}>폰으로 촬영하기</b>
        <span style={css('font-size:14.5px;line-height:1.6;color:#5B6472')}>폰 카메라로 QR 을 찍으면 이 회차의 촬영 화면이 열려요.<br />이 웹과 같은 계정으로 로그인한 뒤 찍어 주세요.</span>
        {qr ? <img src={qr} alt="촬영 화면 QR" width={240} height={240} style={css('border-radius:12px;border:1px solid #ECE8E2')} /> : <div style={css('width:240px;height:240px')}></div>}
        <span style={css('font-size:12px;color:#8E949C;word-break:break-all')}>{url}</span>
        <div style={css('display:flex;align-items:center;gap:8px;font-size:15px;font-weight:700;font-variant-numeric:tabular-nums')}>
          <span style={css(`width:8px;height:8px;border-radius:4px;background:${shots ? '#2E8B57' : '#D2601A'}`)}></span>
          {shots ? `폰에서 영상 ${shots}개가 올라왔어요` : '폰에서 올라오기를 기다리는 중…'}
        </div>
        <button type="button" className="bt" onClick={onClose} style={css('margin-top:4px;height:46px;padding:0 24px;border-radius:12px;background:#1B2433;color:#fff;font-size:15px;font-weight:700')}>닫기</button>
      </div>
    </div>
  )
}
