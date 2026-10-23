import { useMemo, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useCreateDog, useDog, useUpdateDog } from '../../api/dogs'
import { BREEDS, LIMB_LABEL, SEX_LABEL, SIZE_LABEL, previewSizeClass } from '../../api/labels'
import type { DogCreate, DogOut, Limb, Sex, SizeClass } from '../../api/types'
import { useToast } from '../../app/toast'
import { useIsDesktop } from '../../app/useIsDesktop'
import { Icon } from '../../components/Icon'
import { Button, Empty, Field, Input, Pick, PickGrid, Textarea, TopBar } from '../../components/ui'
import './dogs.css'

interface FormState {
  name: string
  breed: string
  kg: string
  birth: string
  sex: Sex | null
  /** 직접 고른 체급. null 이면 자동 분류(서버가 정함) */
  size: SizeClass | null
  rehab: string
  focus: Limb | null
  memo: string
}

const EMPTY: FormState = { name: '', breed: '', kg: '', birth: '', sex: null, size: null, rehab: '', focus: null, memo: '' }

function fromDog(d: DogOut): FormState {
  return {
    name: d.name,
    breed: d.breed,
    kg: String(d.weight_kg),
    birth: d.birth_year ? String(d.birth_year) : '',
    sex: d.sex,
    size: d.size_class_manual ? d.size_class : null,
    rehab: d.rehab_start_date ?? '',
    focus: d.focus_limb,
    memo: d.memo ?? '',
  }
}

/** 화면 필드 → API 요청(screenPlan 4.3). 비우면 null 을 보낸다(수정 때 "값 비우기"). */
function toBody(f: FormState): DogCreate {
  return {
    name: f.name.trim(),
    breed: f.breed.trim(),
    weight_kg: Number(f.kg),
    size_class: f.size,
    birth_year: f.birth.trim() ? Number(f.birth) : null,
    sex: f.sex,
    rehab_start_date: f.rehab || null,
    focus_limb: f.focus,
    memo: f.memo.trim() || null,
  }
}

const FIELD_MSG: Record<string, string> = {
  name: '이름을 확인해 주세요 (50자까지)',
  breed: '견종을 입력해 주세요',
  weight_kg: '체중은 0.5~100kg 사이로 입력해 주세요',
  birth_year: '출생연도는 1990년부터 올해까지만 돼요',
  rehab_start_date: '재활 시작일은 오늘 이전이어야 해요',
  memo: '메모는 1000자까지 쓸 수 있어요',
}

const TODAY = new Date().toISOString().slice(0, 10)

/** S2 반려견 등록·수정. 디자인 v5 `petNew`. 수정은 반려견을 불러온 뒤 폼을 그린다. */
export function PetFormPage({ mode }: { mode: 'new' | 'edit' }) {
  const { dogId } = useParams()
  const dogQ = useDog(mode === 'edit' ? dogId : undefined)

  if (mode === 'edit') {
    if (dogQ.isError) {
      return (
        <div className="screen">
          <TopBar title="반려견 정보 수정" />
          <div className="screen-body">
            <Empty>{dogQ.error instanceof ApiError ? dogQ.error.message : '반려견 정보를 불러오지 못했어요'}</Empty>
          </div>
        </div>
      )
    }
    if (!dogQ.data) {
      return (
        <div className="screen">
          <TopBar title="반려견 정보 수정" />
          <div className="screen-body">
            <div className="skeleton" style={{ height: 240 }} />
          </div>
        </div>
      )
    }
    return <PetForm key={dogQ.data.id} mode="edit" dogId={dogQ.data.id} initial={fromDog(dogQ.data)} />
  }
  return <PetForm mode="new" initial={EMPTY} />
}

function PetForm({ mode, dogId, initial }: { mode: 'new' | 'edit'; dogId?: string; initial: FormState }) {
  const nav = useNavigate()
  const toast = useToast()
  const create = useCreateDog()
  const update = useUpdateDog(dogId ?? '')
  const desktop = useIsDesktop()

  const [f, setF] = useState<FormState>(initial)
  const [fieldErr, setFieldErr] = useState<Record<string, string>>({})
  const [breedFocus, setBreedFocus] = useState(false)

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => {
    setF((s) => ({ ...s, [k]: v }))
    setFieldErr((e) => {
      const apiKey = k === 'kg' ? 'weight_kg' : k === 'birth' ? 'birth_year' : k === 'rehab' ? 'rehab_start_date' : k
      if (!(apiKey in e)) return e
      const { [apiKey]: _drop, ...rest } = e
      return rest
    })
  }

  const kgNum = Number(f.kg)
  const autoSize = previewSizeClass(Number.isFinite(kgNum) ? kgNum : null)
  const shownSize = f.size ?? autoSize
  const ready = f.name.trim() && f.breed.trim() && f.kg.trim() && Number.isFinite(kgNum) && kgNum > 0

  const breedQuery = f.breed.trim().replace(/\s/g, '')
  const breedExact = BREEDS.includes(f.breed.trim())
  const suggestions = useMemo(
    () => (breedQuery ? BREEDS.filter((b) => b.replace(/\s/g, '').includes(breedQuery)).slice(0, 6) : []),
    [breedQuery],
  )
  const showSug = breedFocus && !!breedQuery && !breedExact

  const busy = create.isPending || update.isPending

  async function submit(e?: FormEvent) {
    e?.preventDefault()
    if (!ready) {
      toast('이름·견종·체중을 입력해 주세요')
      return
    }
    try {
      if (mode === 'edit') {
        // 바꾼 필드만 보낸다(api-spec 5절 PATCH). 체급은 직접 선택을 풀었을 때 null 을 보내 자동 분류로 돌린다
        const before = toBody(initial)
        const after = toBody(f)
        const patch: Partial<DogCreate> = {}
        for (const k of Object.keys(after) as (keyof DogCreate)[]) if (after[k] !== before[k]) (patch as Record<string, unknown>)[k] = after[k]
        if (Object.keys(patch).length === 0) {
          toast('바뀐 내용이 없어요')
          nav(-1)
          return
        }
        await update.mutateAsync(patch)
        toast('저장했어요')
        nav(-1)
      } else {
        const dog = await create.mutateAsync(toBody(f))
        toast(`${dog.name} 등록을 마쳤어요`)
        nav(`/dogs/${dog.id}`, { replace: true })
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === 'VALIDATION_ERROR' && err.fields.length) {
        const next: Record<string, string> = {}
        for (const fe of err.fields) next[fe.field] = FIELD_MSG[fe.field] ?? '입력값을 확인해 주세요'
        setFieldErr(next)
        toast(err.message)
      } else {
        toast(err instanceof Error ? err.message : '저장하지 못했어요')
      }
    }
  }

  const title = mode === 'edit' ? '반려견 정보 수정' : '반려견 등록'

  return (
    <form className={`screen${desktop ? ' as-card' : ''}`} onSubmit={submit}>
      <TopBar title={title} />
      <div className="scroll screen-body">
        <div className="photo-slot" aria-hidden="true">
          <Icon name="img" size={22} />
          사진 추가
        </div>

        <Field label="이름" hint={fieldErr.name} hintTone="bad">
          <Input value={f.name} onChange={(e) => set('name', e.target.value)} placeholder="예) 보리" maxLength={50} invalid={!!fieldErr.name} />
        </Field>

        <Field label="견종" hint={fieldErr.breed} hintTone="bad">
          <Input
            value={f.breed}
            onChange={(e) => set('breed', e.target.value)}
            onFocus={() => setBreedFocus(true)}
            onBlur={() => window.setTimeout(() => setBreedFocus(false), 120)}
            placeholder="견종을 입력하면 목록이 떠요"
            maxLength={50}
            invalid={!!fieldErr.breed}
            autoComplete="off"
          />
          {showSug && (
            <div className="suggest">
              {suggestions.map((b) => (
                <button type="button" key={b} className="suggest-item" onMouseDown={(e) => e.preventDefault()} onClick={() => { set('breed', b); setBreedFocus(false) }}>
                  {b}
                </button>
              ))}
              {suggestions.length === 0 && <div className="suggest-none">목록에 없어요 · 입력한 이름으로 등록돼요</div>}
            </div>
          )}
        </Field>

        <Field label="체중 (kg)" hint={fieldErr.weight_kg} hintTone="bad">
          <Input value={f.kg} onChange={(e) => set('kg', e.target.value)} placeholder="예) 28.4" inputMode="decimal" invalid={!!fieldErr.weight_kg} />
        </Field>

        <Field label={<>출생연도 <span className="optional">선택</span></>} hint={fieldErr.birth_year} hintTone="bad">
          <Input value={f.birth} onChange={(e) => set('birth', e.target.value)} placeholder="예) 2019" inputMode="numeric" maxLength={4} invalid={!!fieldErr.birth_year} />
        </Field>

        <Field label={<>성별 <span className="optional">선택</span></>}>
          <PickGrid cols={2}>
            {(Object.keys(SEX_LABEL) as Sex[]).map((k) => (
              <Pick key={k} on={f.sex === k} onClick={() => set('sex', f.sex === k ? null : k)}>
                {SEX_LABEL[k]}
              </Pick>
            ))}
          </PickGrid>
        </Field>

        <Field label="체급" right={f.size ? '직접 선택 · 다시 누르면 자동 분류' : '체중으로 자동 분류돼요'}>
          <PickGrid cols={3}>
            {(Object.keys(SIZE_LABEL) as SizeClass[]).map((k) => (
              <Pick key={k} on={shownSize === k} onClick={() => set('size', f.size === k ? null : k)}>
                {SIZE_LABEL[k]}
              </Pick>
            ))}
          </PickGrid>
        </Field>

        <div className="divider" />
        <b style={{ fontSize: 16 }}>
          재활 정보 <span className="optional">선택</span>
        </b>

        <Field label="재활 시작일" hint={fieldErr.rehab_start_date} hintTone="bad">
          <Input type="date" value={f.rehab} onChange={(e) => set('rehab', e.target.value)} max={TODAY} invalid={!!fieldErr.rehab_start_date} />
        </Field>

        <Field label="관심 다리" right="다시 누르면 선택이 풀려요">
          <PickGrid cols={2}>
            {(Object.keys(LIMB_LABEL) as Limb[]).map((k) => (
              <Pick key={k} on={f.focus === k} onClick={() => set('focus', f.focus === k ? null : k)}>
                {LIMB_LABEL[k]}
              </Pick>
            ))}
          </PickGrid>
        </Field>

        <Field label="내부 메모" hint={fieldErr.memo ?? '담당자 화면에만 보이고 보고서에는 넣지 않아요.'} hintTone={fieldErr.memo ? 'bad' : 'sub'}>
          <Textarea value={f.memo} onChange={(e) => set('memo', e.target.value)} placeholder="예) 수술 후 6주차, 오른뒤 체중 부하 관찰" maxLength={1000} />
        </Field>
      </div>
      <div className="sticky-footer">
        <Button type="submit" dim={!ready} disabled={busy}>
          {busy ? '저장 중…' : mode === 'edit' ? '저장하기' : '등록하기'}
        </Button>
      </div>
    </form>
  )
}
