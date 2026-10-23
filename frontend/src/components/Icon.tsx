/** 디자인 v5 의 <defs> 아이콘을 스프라이트로 둔다. <Icon name="back" /> 로 쓴다. */

export type IconName =
  | 'chev'
  | 'back'
  | 'x'
  | 'check'
  | 'bell'
  | 'user'
  | 'arrow'
  | 'doc'
  | 'cam'
  | 'img'
  | 'org'
  | 'gear'
  | 'headset'
  | 'paw'
  | 'search'

export function IconSprite() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <defs>
        <g id="i-chev">
          <path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        <g id="i-back">
          <path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        <g id="i-x">
          <path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
        </g>
        <g id="i-check">
          <path d="M5 12.5 10 17 19 7" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        <g id="i-bell">
          <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        </g>
        <g id="i-user">
          <circle cx="12" cy="8.5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M5 20c1-4 4-5.5 7-5.5s6 1.5 7 5.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </g>
        <g id="i-arrow">
          <path d="M3 12h17M14 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        <g id="i-doc">
          <path d="M7 3h7l4 4v14H7z M14 3v4h4 M10 12h5M10 16h5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        </g>
        <g id="i-cam">
          <path d="M4 8h3l2-3h6l2 3h3v11H4z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
          <circle cx="12" cy="13" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
        </g>
        <g id="i-img">
          <rect x="4" y="5" width="16" height="14" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
          <circle cx="9" cy="10" r="1.6" fill="currentColor" />
          <path d="M4 17l5-4 4 3 3-2 4 3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        </g>
        <g id="i-org">
          <path d="M4 20V8l8-4 8 4v12M9 20v-5h6v5M4 20h16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
        </g>
        <g id="i-gear">
          <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.7" />
          <path
            d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
          />
        </g>
        <g id="i-headset">
          <path d="M4 14v-2a8 8 0 0 1 16 0v2" fill="none" stroke="currentColor" strokeWidth="1.7" />
          <rect x="3" y="13" width="4" height="6" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.7" />
          <rect x="17" y="13" width="4" height="6" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.7" />
        </g>
        <g id="i-paw">
          <circle cx="6" cy="10" r="2" fill="currentColor" />
          <circle cx="10" cy="6.5" r="2" fill="currentColor" />
          <circle cx="14" cy="6.5" r="2" fill="currentColor" />
          <circle cx="18" cy="10" r="2" fill="currentColor" />
          <path d="M12 11c-3 0-5.5 2.6-5.5 5 0 1.6 1.2 2.5 2.6 2.5 1 0 1.8-.5 2.9-.5s1.9.5 2.9.5c1.4 0 2.6-.9 2.6-2.5 0-2.4-2.5-5-5.5-5z" fill="currentColor" />
        </g>
        <g id="i-search">
          <circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
          <path d="M16 16l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </g>
      </defs>
    </svg>
  )
}

export function Icon({ name, size = 24, className, style }: { name: IconName; size?: number; className?: string; style?: React.CSSProperties }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} style={style} aria-hidden="true">
      <use href={`#i-${name}`} />
    </svg>
  )
}
