import { createBrowserRouter } from 'react-router-dom'

import { DesignRoot } from '../design/DesignRoot'

/**
 * 모든 주소를 DesignRoot 가 받는다. 주소 → 화면 이름 매핑과 로그인 가드는 design/DesignRoot.tsx 의 parseRoute 에 있다.
 * 폭 1024px 이상이면 웹 v2, 미만이면 앱 v5 화면이 같은 주소에서 나온다.
 */
export const router = createBrowserRouter([{ path: '*', element: <DesignRoot /> }])
