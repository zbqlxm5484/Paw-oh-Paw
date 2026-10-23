/** 디자인 v5 의 골격 아이콘(<g id="dogkp">). 결과 목록 썸네일 등에 쓴다. */
export function DogSkeleton({ width = 38, height = 26 }: { width?: number; height?: number }) {
  return (
    <svg width={width} height={height} viewBox="40 10 310 190" aria-hidden="true">
      <polyline points="70,70 120,62 190,60 250,66 285,52" fill="none" stroke="#F2B705" strokeWidth="3" strokeLinecap="round" />
      <polyline points="285,52 300,30 326,44" fill="none" stroke="#F2B705" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points="250,66 262,108 256,146 266,178" fill="none" stroke="#E5604D" strokeWidth="3" opacity=".55" />
      <polyline points="242,68 232,110 244,146 236,178" fill="none" stroke="#3B6FE0" strokeWidth="3.5" />
      <polyline points="92,70 112,114 92,146 104,178" fill="none" stroke="#E5604D" strokeWidth="3" opacity=".55" />
      <polyline points="84,72 70,116 96,148 80,178" fill="none" stroke="#3B6FE0" strokeWidth="3.5" />
      <g fill="#141B22" strokeWidth="2.5">
        {[
          [70, 70, '#F2B705'], [120, 62, '#F2B705'], [190, 60, '#F2B705'], [250, 66, '#F2B705'], [285, 52, '#F2B705'], [326, 44, '#F2B705'],
          [232, 110, '#3B6FE0'], [244, 146, '#3B6FE0'], [236, 178, '#3B6FE0'], [70, 116, '#3B6FE0'], [96, 148, '#3B6FE0'], [80, 178, '#3B6FE0'],
        ].map(([x, y, c], i) => (
          <circle key={i} cx={x as number} cy={y as number} r="5" stroke={c as string} />
        ))}
      </g>
    </svg>
  )
}
