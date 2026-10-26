import { Component, type ComponentType } from 'react'

export type Vals = Record<string, any>

/**
 * 디자인 프로토타입 로직 클래스의 받침. 원본(Claude Design)의 `class Component extends DCLogic` 가
 * renderVals() 로 만든 값을 자동 생성된 View(템플릿 JSX)에 넘기는 구조를 그대로 둔다.
 */
export class DCLogic<P = {}, S = any> extends Component<P, S> {
  static View: ComponentType<{ v: Vals }>
  renderVals(): Vals {
    return {}
  }
  render() {
    const V = (this.constructor as typeof DCLogic).View
    return <V v={this.renderVals()} />
  }
}
