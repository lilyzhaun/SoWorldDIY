type MainFooterProps = { readonly visible: boolean }

export function MainFooter({ visible }: MainFooterProps): React.JSX.Element {
  return (
    <div id="mainFooter" className="footer-note-main" style={{ display: visible ? 'block' : 'none' }}>
      仅供个人学习使用，高净值账号请勿使用本网站。
      <br />
      <span>
        如使用密码登录请于24h内更改密码。
        <br />
        发生一切损失于本网站无关。
      </span>
    </div>
  )
}
