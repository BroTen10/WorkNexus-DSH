/**
 * Desktop 主进程身份装配点。
 *
 * 真实实现必须在装配时注入官方凭据服务适配的 SecureStore；
 * 这里不保存、不落盘、不转发任何企业 Token 到官方会话。
 */

export type DesktopAuthAssembly = {
  controlPlaneBaseUrl: string
  secureStore: 'official-credentials-service-adapter'
}

export const DESKTOP_AUTH_ASSEMBLY: DesktopAuthAssembly = {
  controlPlaneBaseUrl: process.env.WORKNEXUS_CONTROL_PLANE_URL ?? 'http://127.0.0.1:8410',
  secureStore: 'official-credentials-service-adapter',
}
