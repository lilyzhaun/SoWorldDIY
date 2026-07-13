# 宝塔 / 虚拟主机部署遗留配置

根目录不再保留 `.htaccess` / `.user.ini`，避免污染应用代码目录。

如果仍使用宝塔或 PHP 虚拟主机风格部署，可参考 `.user.ini.example` 后按线上路径手动创建。

自定义错误页（`404.html`、`502.html`）已移至 `deploy/bt/static/`，可按需复制到宝塔站点根目录或 Nginx `error_page` 配置路径。
