import { fmtMonthDay } from '../../api/labels'
import type { DogOut } from '../../api/types'

/** 웹 v2 의 반려견 가로 띠(동그란 아바타). 홈·영상 올리기·분석 결과에서 쓴다. */
export function DogStrip({
  dogs,
  selectedId,
  onPick,
  onAdd,
  allOption,
  showMeta,
}: {
  dogs: DogOut[]
  selectedId: string | null
  onPick: (id: string | null) => void
  onAdd?: () => void
  /** "전체" 칩을 맨 앞에 */
  allOption?: boolean
  showMeta?: boolean
}) {
  return (
    <div className="dog-strip">
      {allOption && (
        <button type="button" className={`dog-chip${selectedId === null ? ' on' : ''}`} onClick={() => onPick(null)}>
          <div className="av all">전체</div>
          <div>
            <div className="nm">모든 반려견</div>
          </div>
        </button>
      )}
      {dogs.map((d) => (
        <button type="button" key={d.id} className={`dog-chip${selectedId === d.id ? ' on' : ''}`} onClick={() => onPick(d.id)}>
          <div className="av">
            {d.name.charAt(0)}
            {d.open_session_id && <span className="live">측정 중</span>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span className="nm">{d.name}</span>
            <span className="br">({d.breed})</span>
            {showMeta && <span className="mt tabular">{d.last_measured_on ? `${fmtMonthDay(d.last_measured_on)} · ${d.session_count}회차` : '측정 없음'}</span>}
          </div>
        </button>
      ))}
      {onAdd && (
        <button type="button" className="dog-chip add" onClick={onAdd}>
          <div className="av">+</div>
          <span className="nm">등록</span>
        </button>
      )}
    </div>
  )
}
