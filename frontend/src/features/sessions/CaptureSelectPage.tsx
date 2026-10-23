import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useDogs } from '../../api/dogs'
import { dogDesc } from '../../api/labels'
import { useStartSession } from '../../api/sessions'
import { useToast } from '../../app/toast'
import { Icon } from '../../components/Icon'
import { Avatar, Button, Empty, Field, Input } from '../../components/ui'
import './sessions.css'

/**
 * S3 측정 시작. 디자인 v5 `capSelect`. 반려견을 고르고 그날 체중을 적으면 회차를 만든다(POST /dogs/{id}/sessions).
 * 이미 측정 중인 회차가 있으면(409 SESSION_ALREADY_OPEN) 그 회차로 간다.
 */
export function CaptureSelectPage() {
  const nav = useNavigate()
  const toast = useToast()
  const [sp] = useSearchParams()
  const dogsQ = useDogs({ size: 100 })
  const start = useStartSession()

  const list = dogsQ.data?.items ?? []
  const [picked, setPicked] = useState<string | null>(sp.get('dog'))
  const [weight, setWeight] = useState('')
  const [weightErr, setWeightErr] = useState<string | null>(null)

  const sel = list.find((d) => d.id === picked) ?? (picked ? undefined : list[0])
  const selId = sel?.id ?? null

  async function submit(e?: FormEvent) {
    e?.preventDefault()
    if (!selId) {
      toast('촬영할 반려견을 골라 주세요')
      return
    }
    if (sel?.open_session_id) {
      nav(`/sessions/${sel.open_session_id}`, { replace: true })
      return
    }
    const w = weight.trim()
    const num = w ? Number(w) : null
    if (w && (!Number.isFinite(num) || num! < 0.5 || num! > 100)) {
      setWeightErr('체중은 0.5~100kg 사이로 입력해 주세요')
      return
    }
    try {
      const s = await start.mutateAsync({ dogId: selId, body: { weight_kg: num } })
      nav(`/sessions/${s.id}`, { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'SESSION_ALREADY_OPEN') {
        const sid = err.detail?.session_id
        if (typeof sid === 'string') {
          toast('진행 중인 회차로 이어서 측정해요')
          nav(`/sessions/${sid}`, { replace: true })
          return
        }
      }
      if (err instanceof ApiError && err.code === 'VALIDATION_ERROR' && err.fields.some((f) => f.field === 'weight_kg')) {
        setWeightErr('체중은 0.5~100kg 사이로 입력해 주세요')
        return
      }
      toast(err instanceof Error ? err.message : '회차를 시작하지 못했어요')
    }
  }

  return (
    <form className="screen" onSubmit={submit}>
      <div className="topbar">
        <div className="topbar-left">
          <button type="button" className="icon-btn" onClick={() => nav(-1)} aria-label="닫기">
            <Icon name="x" />
          </button>
          <b className="topbar-title">보행 분석</b>
        </div>
      </div>
      <div className="scroll screen-body" style={{ gap: 12 }}>
        <h1 style={{ fontSize: 22, marginBottom: 8 }}>어느 반려견을 촬영할까요?</h1>

        {dogsQ.isPending && <div className="skeleton" />}
        {dogsQ.isSuccess && list.length === 0 && (
          <Empty>
            등록된 반려견이 없어요.
            <div style={{ marginTop: 12 }}>
              <Button size="md" style={{ width: 'auto', padding: '0 18px', margin: '0 auto' }} onClick={() => nav('/dogs/new')}>
                반려견 등록하기
              </Button>
            </div>
          </Empty>
        )}
        {list.map((d) => {
          const on = d.id === selId
          return (
            <button type="button" key={d.id} className={`cap-dog${on ? ' on' : ''}`} onClick={() => setPicked(d.id)} aria-pressed={on}>
              <Avatar name={d.name} size={44} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {d.name}
                  {d.open_session_id && <span className="live-chip">측정 중</span>}
                </div>
                <div style={{ fontSize: 13, color: 'var(--sub)' }}>{dogDesc(d)}</div>
              </div>
              <span className="radio">
                <span />
              </span>
            </button>
          )
        })}

        <Field
          label={<>오늘 체중 <span className="optional">선택</span></>}
          hint={weightErr ?? '재활 중 체중이 바뀌면 그날 기준으로 비교해요. 비우면 등록 체중을 써요.'}
          hintTone={weightErr ? 'bad' : 'sub'}
        >
          <div style={{ position: 'relative', display: 'flex' }}>
            <Input
              value={weight}
              onChange={(e) => {
                setWeight(e.target.value)
                setWeightErr(null)
              }}
              placeholder={sel ? `등록 체중 ${sel.weight_kg}` : '예) 28.1'}
              inputMode="decimal"
              invalid={!!weightErr}
              style={{ paddingRight: 44 }}
              disabled={!!sel?.open_session_id}
            />
            <span className="input-unit">kg</span>
          </div>
        </Field>

        <div className="checklist">
          <b style={{ fontSize: 14 }}>촬영 전 확인해 주세요</b>
          <span>
            <Icon name="check" size={18} /> 걷는 방향과 직각, 옆모습이 보이게
          </span>
          <span>
            <Icon name="check" size={18} /> 휴대폰은 가로로, 몸 전체가 화면 안에
          </span>
          <span>
            <Icon name="check" size={18} /> 매트를 왕복해 걷게 하고, 양쪽 방향 모두 권장 통과 수를 채워요
          </span>
        </div>
      </div>
      <div className="sticky-footer" style={{ borderTop: 0 }}>
        <Button type="submit" disabled={start.isPending || !selId}>
          <Icon name="cam" size={20} />
          {sel?.open_session_id ? '이어서 측정' : start.isPending ? '회차 만드는 중…' : '측정 시작'}
        </Button>
      </div>
    </form>
  )
}
