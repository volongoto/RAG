import Cookies from 'js-cookie'

const STORAGE_PREFIX = 'cradle'
const TokenKey = `${STORAGE_PREFIX}-Admin-Token`
export const UsernameKey = `${STORAGE_PREFIX}-username`
export const PasswordKey = `${STORAGE_PREFIX}-password`
export const RememberMeKey = `${STORAGE_PREFIX}-rememberMe`
export const SidebarStatusKey = `${STORAGE_PREFIX}-sidebarStatus`
export const SizeKey = `${STORAGE_PREFIX}-size`
export const LayoutSettingKey = `${STORAGE_PREFIX}-layout-setting`

export function getToken() {
  return Cookies.get(TokenKey)
}

export function setToken(token) {
  return Cookies.set(TokenKey, token)
}

export function removeToken() {
  return Cookies.remove(TokenKey)
}
