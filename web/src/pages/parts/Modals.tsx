// _modals.html 의 모달들 + static/pet.js(반려견 등록·수정 모달 동작). 각 화면에서 필요한 것만 Base 의 modals 로 넣는다.
// 열고 닫기는 Base(app.js)가 한다: data-open="id" / data-close / window.ppOpen(id).
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { css } from '../../app/css'
import { PostForm } from '../../app/page'
import { current } from '../../app/session'
import { BREEDS, LARGE_BREEDS, LIMB, SEX, SIZE, SMALL_BREEDS, STAGE_NAMES } from '../../config'
import type { Dog } from '../../store/types'

declare global {
  interface Window {
    ppOpenPet?: (id: string) => void
  }
}

/** open_modal(id) + close_modal(): 시제품은 여는 매크로·닫는 매크로 둘로 나눴지만 여기선 children 으로 감싼다 */
export function OpenModal({ id, children }: { id: string; children?: ReactNode }) {
  return (
    <div id={id} className="pp-modal no-print" style={css('position:fixed;inset:0;background:rgba(14,18,23,.5);z-index:50;display:none;align-items:center;justify-content:center;padding:24px')}>
      <div style={css('width:100%;max-width:460px;max-height:calc(100vh - 48px);overflow:auto;background:#fff;border-radius:22px;padding:28px;display:flex;flex-direction:column;gap:20px;position:relative')}>
        <div data-close="" style={css('position:absolute;right:14px;top:14px;width:40px;height:40px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#5B6472')}><svg width="22" height="22" viewBox="0 0 24 24"><use href="#w-x"></use></svg></div>
        {children}
      </div>
    </div>
  )
}

/** close_modal(): JSX 에서는 OpenModal 이 닫는 태그까지 그리므로 빈 조각(이름 맞춤용) */
export function CloseModal() {
  return null
}

const showModal = (id: string) => {
  if (window.ppOpen) window.ppOpen(id)
  else {
    const m = document.getElementById(id)
    if (m) m.style.display = 'flex'
  }
}

// ── 반려견 등록 · 수정 (pet_modal + pet.js) ──
const FI = 'height:50px;border-radius:12px;border:1px solid #ECE8E2;padding:0 16px;font-size:15px;color:#1B2433;outline:none'

interface PetState {
  dog: Dog | null
  name: string
  breed: string
  kg: string
  birth: string
  rehab: string
  memo: string
  sex: string
  size: string
  focus: string
  no: string
  owner: string
  phone: string
  stage: string
}

const EMPTY: PetState = { dog: null, name: '', breed: '', kg: '', birth: '', rehab: '', memo: '', sex: 'm', size: '', focus: '', no: '', owner: '', phone: '', stage: 'rehab' }

function dogsNow(dogs?: Dog[]): Dog[] {
  if (dogs) return dogs
  try {
    return current()?.dogs || []
  } catch {
    return []
  }
}

/**
 * pet_modal(next_url) + pet.js. data-pet="new" 또는 data-pet="<반려견 id>" 를 누르면 열린다(window.ppOpenPet 도 같음).
 * open=true 면 처음에 새 등록으로 연다(시제품의 ?modal=pet → window.PP.openPet). dogs 를 안 주면 로그인한 기관의 반려견에서 찾는다.
 */
export function PetModal({ next_url, open = false, dogs }: { next_url: string; open?: boolean; dogs?: Dog[] }) {
  const [s, setS] = useState<PetState>(EMPTY)
  const dogsRef = useRef(dogs)
  dogsRef.current = dogs

  useEffect(() => {
    const openPet = (id: string) => {
      const d = id && id !== 'new' ? dogsNow(dogsRef.current).find((x) => x.id === id) || null : null
      setS({
        dog: d,
        name: d ? d.name || '' : '',
        breed: d ? d.breed || '' : '',
        kg: d ? d.kg || '' : '',
        birth: d ? d.birth || '' : '',
        rehab: d ? d.rehab || '' : '',
        memo: d ? d.memo || '' : '',
        sex: d ? d.sex || 'm' : 'm',
        size: d && d.size_manual ? d.size : '',
        focus: d && d.focus ? d.focus : '',
        no: d ? d.no || '' : '',
        owner: d ? d.owner || '' : '',
        phone: d ? d.phone || '' : '',
        stage: d ? d.stage || 'rehab' : 'rehab',
      })
      showModal('petModal')
    }
    window.ppOpenPet = openPet
    const onClick = (e: MouseEvent) => {
      const t = (e.target as HTMLElement).closest?.('[data-pet]') as HTMLElement | null
      if (t) {
        e.preventDefault()
        e.stopPropagation()
        openPet(t.dataset.pet || '')
      }
    }
    document.addEventListener('click', onClick, true)
    if (open) openPet('new')
    return () => {
      document.removeEventListener('click', onClick, true)
      if (window.ppOpenPet === openPet) delete window.ppOpenPet
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const autoSize = () => {
    const b = s.breed
    const kg = Number(s.kg)
    if (SMALL_BREEDS.indexOf(b) >= 0) return 'S'
    if (LARGE_BREEDS.indexOf(b) >= 0) return 'L'
    if (BREEDS.indexOf(b) >= 0 && b !== '믹스견') return 'M'
    return kg ? (kg < 10 ? 'S' : kg < 25 ? 'M' : 'L') : 'M'
  }
  const cur = (f: 'sex' | 'size' | 'focus') => s[f] || (f === 'size' ? autoSize() : '')
  const pick = (f: 'sex' | 'size' | 'focus', val: string, toggle: boolean) =>
    setS((p) => ({ ...p, [f]: toggle && p[f] === val ? '' : val }))
  const pickStyle = (f: 'sex' | 'size' | 'focus', val: string, fs: string) => {
    // pet.js 의 paint(): 고른 칸만 주황 테두리·배경
    const on = cur(f) === val
    return css(`height:46px;border-radius:12px;border:1.5px solid ${on ? '#D2601A' : '#ECE8E2'};background:${on ? '#FCEEE3' : '#fff'};color:${on ? '#A8481A' : '#3A4250'};display:flex;align-items:center;justify-content:center;font-size:${fs};font-weight:600;cursor:pointer`)
  }
  const ready = !!(s.name && s.breed && s.kg)

  // 견종 자동완성
  const q = s.breed.trim().replace(/\s/g, '')
  const exact = BREEDS.indexOf(s.breed) >= 0
  const list = q ? BREEDS.filter((b) => b.replace(/\s/g, '').indexOf(q) >= 0).slice(0, 6) : []
  const showSug = !!q && !exact

  const set = (k: 'name' | 'breed' | 'kg' | 'birth' | 'rehab' | 'memo' | 'no' | 'owner' | 'phone' | 'stage') => (e: { currentTarget: { value: string } }) => {
    const v = e.currentTarget.value
    setS((p) => ({ ...p, [k]: v }))
  }

  return (
    <OpenModal id="petModal">
      <PostForm action="/dogs" id="petForm" style={css('display:contents')}
        onBefore={() => {
          if (!ready) {
            window.ppToast('이름·견종·체중을 입력해 주세요')
            return false
          }
        }}>
        <input type="hidden" name="dog_id" value={s.dog ? s.dog.id : ''} /><input type="hidden" name="version" value={s.dog ? String(s.dog.version) : ''} />
        <input type="hidden" name="next_url" value={next_url} />
        <input type="hidden" name="sex" value={s.sex} /><input type="hidden" name="size" value={s.size} /><input type="hidden" name="focus" value={s.focus} />
        <b id="petTitle" style={css('font-size:22px;letter-spacing:-0.5px')}>{s.dog ? '반려견 정보 수정' : '반려견 등록'}</b>
        <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>이름</span><input className="inp" name="name" placeholder="예) 보리" autoComplete="off" style={css(FI)} value={s.name} onChange={set('name')} /></label>
        <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>견종</span><input className="inp" name="breed" placeholder="견종을 입력하면 목록이 뜹니다" autoComplete="off" style={css(FI)} value={s.breed} onChange={set('breed')} />
          <div id="breedSug" style={css(`border:1px solid #ECE8E2;border-radius:12px;box-shadow:0 10px 24px rgba(27,36,51,.1);overflow:hidden;display:${showSug ? 'flex' : 'none'};flex-direction:column`)}>
            {showSug && list.map((name, i) => (
              <div key={name} className="hv-menu" style={css('min-height:44px;padding:0 16px;display:flex;align-items:center;font-size:15px;cursor:pointer;border-top:' + (i ? '1px solid #F2EFEA' : 'none'))}
                onMouseDown={(e) => {
                  e.preventDefault()
                  setS((p) => ({ ...p, breed: name }))
                }}>{name}</div>
            ))}
            {showSug && !list.length ? <div style={css('min-height:44px;padding:0 16px;display:flex;align-items:center;font-size:14px;color:#5B6472')}>목록에 없습니다. 입력한 이름으로 등록됩니다</div> : null}
          </div>
        </label>
        <div style={css('display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px')}>
          <label style={css('display:flex;flex-direction:column;gap:8px;min-width:0')}><span style={css('font-size:14px;font-weight:600')}>체중 (kg)</span><input className="inp" name="kg" inputMode="decimal" placeholder="예) 28.4" style={css(`${FI};min-width:0`)} value={s.kg} onChange={set('kg')} /></label>
          <label style={css('display:flex;flex-direction:column;gap:8px;min-width:0')}><span style={css('font-size:14px;font-weight:600')}>출생연도 <span style={css('color:#5B6472;font-weight:500')}>선택</span></span><input className="inp" name="birth" inputMode="numeric" placeholder="예) 2019" style={css(`${FI};min-width:0`)} value={s.birth} onChange={set('birth')} /></label>
        </div>
        <div style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>성별</span>
          <div style={css('display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px')}>{Object.entries(SEX).map(([k, label]) => <div key={k} className="pick" data-field="sex" data-val={k} style={pickStyle('sex', k, '15px')} onClick={() => pick('sex', k, false)}>{label}</div>)}</div>
        </div>
        <div style={css('display:flex;flex-direction:column;gap:8px')}>
          <div style={css('display:flex;align-items:baseline;justify-content:space-between;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>체급</span><span id="sizeNote" style={css('font-size:13px;color:#5B6472')}>{s.size ? '직접 선택. 다시 누르면 자동 분류' : '견종·체중으로 자동 분류됩니다'}</span></div>
          <div style={css('display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px')}>{Object.entries(SIZE).map(([k, label]) => <div key={k} className="pick" data-field="size" data-val={k} data-toggle="1" style={pickStyle('size', k, '15px')} onClick={() => pick('size', k, true)}>{label}</div>)}</div>
        </div>
        <div style={css('height:1px;background:#ECE8E2')}></div>
        {/* 동물번호·보호자·단계(271). 보고서에는 들어가지 않는다 */}
        <b style={css('font-size:15px')}>차트 정보 <span style={css('font-size:14px;font-weight:500;color:#5B6472')}>선택</span></b>
        <div style={css('display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px')}>
          <label style={css('display:flex;flex-direction:column;gap:8px;min-width:0')}><span style={css('font-size:14px;font-weight:600')}>동물번호</span><input className="inp" name="no" placeholder="예) A-1024" autoComplete="off" style={css(`${FI};min-width:0`)} value={s.no} onChange={set('no')} /></label>
          <label style={css('display:flex;flex-direction:column;gap:8px;min-width:0')}><span style={css('font-size:14px;font-weight:600')}>단계</span><select name="stage" style={css(`${FI};min-width:0;background-color:#fff;font-family:inherit`)} value={s.stage} onChange={set('stage')}>{Object.entries(STAGE_NAMES).map(([k, x]) => <option key={k} value={k}>{x}</option>)}</select></label>
          <label style={css('display:flex;flex-direction:column;gap:8px;min-width:0')}><span style={css('font-size:14px;font-weight:600')}>보호자 이름</span><input className="inp" name="owner" placeholder="예) 김보호" autoComplete="off" style={css(`${FI};min-width:0`)} value={s.owner} onChange={set('owner')} /></label>
          <label style={css('display:flex;flex-direction:column;gap:8px;min-width:0')}><span style={css('font-size:14px;font-weight:600')}>보호자 연락처</span><input className="inp" name="phone" inputMode="tel" placeholder={s.dog && !s.phone && s.dog.phone4 ? `뒤 4자리 ${s.dog.phone4}` : '예) 010-1234-5678'} autoComplete="off" style={css(`${FI};min-width:0`)} value={s.phone} onChange={set('phone')} /></label>
        </div>
        <div style={css('height:1px;background:#ECE8E2')}></div>
        <b style={css('font-size:15px')}>재활 정보 <span style={css('font-size:14px;font-weight:500;color:#5B6472')}>선택</span></b>
        <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>재활 시작일</span><input className="inp" type="date" name="rehab" style={css(`${FI};font-family:inherit`)} value={s.rehab} onChange={set('rehab')} /></label>
        <div style={css('display:flex;flex-direction:column;gap:8px')}>
          <div style={css('display:flex;align-items:baseline;justify-content:space-between;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>관심 다리</span><span style={css('font-size:13px;color:#5B6472')}>다시 누르면 선택이 풀립니다</span></div>
          <div style={css('display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px')}>{Object.entries(LIMB).map(([k, label]) => <div key={k} className="pick" data-field="focus" data-val={k} data-toggle="1" style={pickStyle('focus', k, '15px')} onClick={() => pick('focus', k, true)}>{label}</div>)}</div>
        </div>
        <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>내부 메모</span><textarea className="inp" name="memo" placeholder="예) 수술 후 6주차, 오른뒤 체중 부하 관찰" style={css('min-height:88px;border-radius:12px;border:1px solid #ECE8E2;padding:12px 16px;font-size:15px;line-height:1.5;color:#1B2433;outline:none;resize:vertical;font-family:inherit')} value={s.memo} onChange={set('memo')}></textarea></label>
        <button className="bt" type="submit" id="petCta" style={css(`height:54px;border-radius:14px;background:${ready ? '#D2601A' : '#C3C8CF'};color:#fff;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;flex:none`)}>{s.dog ? '저장하기' : '등록하기'}</button>
      </PostForm>
    </OpenModal>
  )
}

// ── 영상 촬영 방법 ──
const GUIDE: [string, string][] = [
  ['휴대폰은 가로로', '세로 영상은 분석할 수 없습니다. 화면을 가로로 돌려 찍어 주세요.'],
  ['옆에서, 걷는 방향과 직각으로', '반려견의 옆모습 전체가 보이도록 2~3m 떨어져서 찍어 주세요.'],
  ['몸 전체가 화면 안에', '머리부터 꼬리, 네 발까지 화면 밖으로 나가지 않게 해 주세요.'],
  ['한 번에 4초, 16개까지', '평평한 바닥에서 뛰지 않고, 멈추거나 앉지 않고, 일직선으로 걷는 모습을 4초씩 차례대로 찍어 주세요.'],
]

export function GuideModal() {
  return (
    <OpenModal id="guideModal">
      <b style={css('font-size:22px;letter-spacing:-0.5px')}>영상 촬영 방법</b>
      <div style={css('display:flex;flex-direction:column;gap:16px')}>
        {GUIDE.map(([t, d], i) => (
          <div key={i} style={css('display:flex;gap:14px')}><span style={css('width:28px;height:28px;border-radius:50%;background:#FCEEE3;color:#A8481A;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;flex:none')}>{i + 1}</span><div style={css('display:flex;flex-direction:column;gap:3px;padding-top:3px')}><b style={css('font-size:15px')}>{t}</b><span style={css('font-size:14px;line-height:1.55;color:#5B6472')}>{d}</span></div></div>
        ))}
      </div>
      <div data-close="" style={css('height:52px;border-radius:14px;background:#D2601A;color:#fff;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;cursor:pointer')}>확인</div>
    </OpenModal>
  )
}

export function LogoutModal() {
  return (
    <OpenModal id="logoutModal">
      <b style={css('font-size:22px;letter-spacing:-0.5px')}>로그아웃하시겠습니까?</b>
      <PostForm action="/logout" style={css('display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0')}>
        <div data-close="" style={css('height:52px;border-radius:14px;background:#F2EEE8;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:600;cursor:pointer')}>취소</div>
        <button className="bt" type="submit" style={css('height:52px;border-radius:14px;background:#1B2433;color:#fff;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700')}>로그아웃</button>
      </PostForm>
    </OpenModal>
  )
}

/**
 * 반려견 삭제 확인. 시제품은 my.html 스크립트가 #delName 글자와 #delForm action 을 바꾼 뒤 연다.
 * 여기선 name·action 을 props 로 받는다(화면이 상태로 들고 있다가 data-open="delModal" 또는 window.ppOpen('delModal') 로 연다).
 */
export function DeleteModal({ name = '', action = '', desc = '' }: { name?: string; action?: string; desc?: string }) {
  return (
    <OpenModal id="delModal">
      <b style={css('font-size:22px;letter-spacing:-0.5px')}><span id="delName">{name}</span> 정보를 삭제하시겠습니까?</b>
      {desc ? <span style={css('font-size:14px;color:#3A4250;padding:10px 12px;border-radius:10px;background:#F7F4EF')}>{name}, {desc}</span> : null}
      <span style={css('font-size:15px;line-height:1.6;color:#5B6472')}>측정 이력과 보고서도 함께 휴지통으로 옮겨지고, 30일 동안은 마이페이지의 ‘반려견 복구’에서 되돌릴 수 있습니다.</span>
      <PostForm action={action} id="delForm" style={css('display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0')}>
        <div data-close="" style={css('height:52px;border-radius:14px;background:#F2EEE8;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:600;cursor:pointer')}>취소</div>
        <button className="bt" type="submit" style={css('height:52px;border-radius:14px;background:#D2601A;color:#fff;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700')}>삭제</button>
      </PostForm>
    </OpenModal>
  )
}
