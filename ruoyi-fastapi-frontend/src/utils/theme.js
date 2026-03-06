export function handleThemeStyle(theme) {
  const root = document.documentElement
  const accentBlue = getDarkColor(theme, 0.2)
  const accentMagenta = shiftHue(theme, 32)

  root.style.setProperty('--el-color-primary', theme)
  root.style.setProperty('--accent-cyan', theme)
  root.style.setProperty('--accent-blue', accentBlue)
  root.style.setProperty('--accent-magenta', accentMagenta)
  root.style.setProperty('--menu-active-text', theme)
  root.style.setProperty('--route-loader', `linear-gradient(90deg, ${theme}, ${accentBlue} 52%, ${accentMagenta} 100%)`)

  for (let i = 1; i <= 9; i += 1) {
    root.style.setProperty(`--el-color-primary-light-${i}`, getLightColor(theme, i / 10))
  }
  for (let i = 1; i <= 9; i += 1) {
    root.style.setProperty(`--el-color-primary-dark-${i}`, getDarkColor(theme, i / 10))
  }
}

export function hexToRgb(str) {
  const source = str.replace('#', '')
  const hex = source.length === 3 ? source.split('').map((item) => `${item}${item}`).join('') : source
  const hexs = hex.match(/../g)
  return [parseInt(hexs[0], 16), parseInt(hexs[1], 16), parseInt(hexs[2], 16)]
}

export function rgbToHex(r, g, b) {
  const hexs = [r, g, b].map((item) => {
    const value = item.toString(16)
    return value.length === 1 ? `0${value}` : value
  })
  return `#${hexs.join('')}`
}

export function getLightColor(color, level) {
  const rgb = hexToRgb(color)
  for (let i = 0; i < 3; i += 1) {
    rgb[i] = Math.floor((255 - rgb[i]) * level + rgb[i])
  }
  return rgbToHex(rgb[0], rgb[1], rgb[2])
}

export function getDarkColor(color, level) {
  const rgb = hexToRgb(color)
  for (let i = 0; i < 3; i += 1) {
    rgb[i] = Math.floor(rgb[i] * (1 - level))
  }
  return rgbToHex(rgb[0], rgb[1], rgb[2])
}

function shiftHue(color, hueShift) {
  const [r, g, b] = hexToRgb(color)
  const [h, s, l] = rgbToHsl(r, g, b)
  const shiftedHue = (h + hueShift + 360) % 360
  const [nr, ng, nb] = hslToRgb(shiftedHue, s, l)
  return rgbToHex(nr, ng, nb)
}

function rgbToHsl(r, g, b) {
  const nr = r / 255
  const ng = g / 255
  const nb = b / 255
  const max = Math.max(nr, ng, nb)
  const min = Math.min(nr, ng, nb)
  const diff = max - min
  let h = 0
  let s = 0
  const l = (max + min) / 2

  if (diff !== 0) {
    s = l > 0.5 ? diff / (2 - max - min) : diff / (max + min)
    switch (max) {
      case nr:
        h = (ng - nb) / diff + (ng < nb ? 6 : 0)
        break
      case ng:
        h = (nb - nr) / diff + 2
        break
      default:
        h = (nr - ng) / diff + 4
        break
    }
    h *= 60
  }

  return [h, s, l]
}

function hslToRgb(h, s, l) {
  if (s === 0) {
    const gray = Math.round(l * 255)
    return [gray, gray, gray]
  }

  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  const hk = h / 360

  const t = [hk + 1 / 3, hk, hk - 1 / 3]
  const rgb = t.map((item) => {
    let c = item
    if (c < 0) c += 1
    if (c > 1) c -= 1
    if (c < 1 / 6) return p + (q - p) * 6 * c
    if (c < 1 / 2) return q
    if (c < 2 / 3) return p + (q - p) * (2 / 3 - c) * 6
    return p
  })

  return rgb.map((item) => Math.round(item * 255))
}
