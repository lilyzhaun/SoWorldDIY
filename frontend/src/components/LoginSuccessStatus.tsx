type LoginSuccessStatusProps = {
  readonly durationMs: number
}

export function LoginSuccessStatus({ durationMs }: LoginSuccessStatusProps): JSX.Element {
  return (
    <div className="login-success-status" role="status" aria-live="polite" aria-atomic="true">
      <div className="login-success-icon" aria-hidden="true">
        <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
          <path d="M5.25 10.25 8.5 13.5l6.25-7" />
        </svg>
      </div>
      <div className="login-success-copy">
        <div className="login-success-title">登录成功</div>
        <div className="login-success-subtitle">正在进入控制台</div>
      </div>
      <div className="login-success-progress" aria-hidden="true">
        <div className="login-success-progress-fill" style={{ animationDuration: `${durationMs}ms` }}></div>
      </div>
    </div>
  )
}
