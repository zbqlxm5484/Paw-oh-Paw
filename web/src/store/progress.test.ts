// 분석 진행: 백엔드 회차는 시간이 아니라 서버의 촬영·회차 상태를 따른다(11-09)
import { describe, expect, it } from 'vitest'
import { jobProgress, jobStep } from './db'
import type { Job } from './types'

const STEPS = ['업로드 완료', '반려견 찾는 중', '관절점 찾는 중', '보행 수치 계산 중', '보고서 만드는 중']
const job = (srv?: Job['srv']): Job => ({ id: 's1', dog: 'd1', n: 16, w: '17.9', started: Date.now() - 600_000, videos: [], result_id: null, notified: false, by: '', remote: true, srv })

describe('백엔드 회차 진행', () => {
  it('오래 기다려도 서버가 영상을 다 분석하기 전에는 98% 로 채우지 않는다', () => {
    const j = job({ status: 'MEASURING', total: 16, done: 4 })
    expect(jobProgress(j) / 5).toBeLessThan(0.5)
    expect(jobStep(j, STEPS)).toBe('영상 분석 중 4/16')
  })
  it('영상이 다 끝나고 회차 결과를 계산하는 동안', () => {
    const j = job({ status: 'AGGREGATING', total: 16, done: 16 })
    expect(Math.round((jobProgress(j) / 5) * 100)).toBe(84)
    expect(jobStep(j, STEPS)).toBe('회차 결과 계산 중')
  })
  it('서버 상태를 아직 못 읽었으면 시작 단계', () => {
    expect(jobStep(job(), STEPS)).toBe('분석을 시작하는 중')
  })
})
