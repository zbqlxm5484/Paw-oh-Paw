// _vital.html: 바이탈 값 하나. 참고 범위를 벗어나면 빨간 글자 + H/L(EMR 검사 결과 표시와 같은 방식), 마우스를 올리면 참고 범위
import { css } from '../../app/css'

/** views.vital_flags 의 한 칸 */
export interface VFlag {
  m?: string
  c?: string
  ref?: string
}

export function VV({ value, f, size = 15, badge = true }: { value: string | number | undefined | null; f?: VFlag | null; size?: number; badge?: boolean }) {
  return (
    <b title={f ? f.ref ?? '' : ''} style={css(`font-size:${size}px;white-space:nowrap;${f && f.c ? 'color:' + f.c : ''}`)}>{value}{badge && f && f.m ? <span style={css(`margin-left:3px;padding:0 5px;border-radius:5px;background:${f.c == '#C2412D' ? '#FBE0D9' : '#FBEBC8'};font-size:12px;font-weight:800;vertical-align:2px`)}>{f.m}</span> : null}</b>
  )
}

/** 표시만 따로(좁은 칸에서 값 옆이 아니라 항목 이름 옆에 둘 때) */
export function VFlagBadge({ f }: { f?: VFlag | null }) {
  return f && f.m ? <span style={css(`margin-left:4px;padding:0 5px;border-radius:5px;background:${f.c == '#C2412D' ? '#FBE0D9' : '#FBEBC8'};color:${f.c};font-size:12px;font-weight:800`)}>{f.m}</span> : null
}

export default VV
