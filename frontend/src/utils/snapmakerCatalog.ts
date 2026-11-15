// Snapmaker EU product variants, captured on 2026-11-06.
type CatalogVariant = [id: string, color: string, hex: string, secondaryHex?: string]

interface CatalogFamily {
  name: string
  material: string
  url: string
  fullSpectrum?: boolean
  variants: CatalogVariant[]
}

const snapSpeedUrl = 'https://eu.snapmaker.com/products/snapspeed-pla-filament'

export const snapmakerCatalog: CatalogFamily[] = [
  {
    name: 'Glow Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/pla-glow-filament-1kg',
    variants: [
      ['50879127257227', 'Green', '#A1FFAC'],
      ['50879127421067', 'Blue', '#7AC0E9'],
      ['50879127584907', 'Yellow', '#F8FF80'],
      ['50879127748747', 'Orange', '#FF9D5B'],
      ['50879127912587', 'Pink', '#F17B8F'],
    ]
  },
  {
    name: 'ABS Filament',
    material: 'ABS',
    url: 'https://eu.snapmaker.com/products/abs-filament-1kg',
    variants: [
      ['48853786067083', 'White', '#FFFFFF'],
      ['48853786230923', 'Black', '#000000'],
      ['48853786394763', 'Yellow', '#FFB81C'],
      ['48853786558603', 'Red', '#DE4343'],
      ['48853786722443', 'Green', '#3A913F'],
      ['48853786886283', 'Orange', '#FF6A13'],
      ['48853787050123', 'Purple', '#6E3FA3'],
      ['48853787213963', 'Light Blue', '#5BC2E7'],
      ['48853787377803', 'Navy Blue', '#002677'],
      ['48853787541643', 'Dark Gray', '#54585A'],
    ]
  },
  {
    name: 'SnapSpeed Filament',
    material: 'PLA',
    url: snapSpeedUrl,
    variants: [
      ['46217784262795', 'Pink', '#FFC0CB'],
      ['46217784295563', 'Cream', '#FFF5E0'],
      ['46217784328331', 'Cool White', '#D9DFE5'],
      ['46217784361099', 'Magenta', '#F24574'],
      ['46217784393867', 'Sky Blue', '#5EBDDB'],
      ['46217784426635', 'Bright Yellow', '#F8F81C'],
      ['46217784459403', 'Olive Green', '#AFC33C'],
      ['46217784492171', 'Blue Gray', '#94B7C9'],
      ['46217784524939', 'Warm Beige', '#C19E86'],
      ['46217784557707', 'Cocoa Brown', '#674B47'],
      ['45009649598603', 'Blue', '#003776'],
      ['45009649565835', 'Green', '#2D9E59'],
      ['45009649500299', 'Grey', '#8C9099'],
      ['45009649696907', 'Purple', '#6C5BB1'],
      ['45009649729675', 'Brown', '#6F4C2F'],
      ['45009649631371', 'Orange', '#F97429'],
      ['45009649434763', 'Black', '#080A0D'],
      ['45009649664139', 'Yellow', '#F4C032'],
      ['45009649467531', 'Pearl White', '#E2DEDB'],
      ['45009649533067', 'Red', '#E72F1D'],
      ['51039038275723', 'Turquoise Blue', '#53D6D0'],
      ['51039038308491', 'Azure Blue', '#0066D9'],
      ['51039038341259', 'Charcoal Gray', '#485259'],
      ['51039038374027', 'Burgundy Red', '#911821'],
      ['51039038406795', 'Peach Beige', '#EEDDD2'],
      ['51039038439563', 'Caramel Brown', '#CB8748'],
      ['51039038472331', 'Army Green', '#31532E'],
      ['51039038505099', 'Mint Green', '#AFD6C1'],
      ['51039038537867', 'Light Purple', '#D3D0EB'],
      ['51039038570635', 'Plum Purple', '#660066'],
    ]
  },
  {
    name: 'ASA Filament',
    material: 'ASA',
    url: 'https://eu.snapmaker.com/products/asa-filament-1kg',
    variants: [
      ['48853787705483', 'Yellow', '#FFE800'],
      ['48853787869323', 'Red', '#AF231C'],
      ['48853788033163', 'Dark Gray', '#53565A'],
      ['48853788197003', 'Carbon Black', '#161618'],
      ['48853788360843', 'White', '#FFFFFF'],
    ]
  },
  {
    name: 'ABS Filament (without RFID)',
    material: 'ABS',
    url: 'https://eu.snapmaker.com/products/abs-filament-1-kg',
    variants: [
      ['40701280059531', 'Black', '#000000'],
      ['40701280092299', 'White', '#FFFFFF'],
    ]
  },
  {
    name: 'Breakaway Support for PLA',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/breakaway-support-for-pla-500g',
    variants: [
      ['40701280223371', 'Natural', ''],
    ]
  },
  {
    name: 'Glow-in-the-Dark Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/glow-in-the-dark-green-pla-filament-1kg',
    variants: [
      ['40739669966987', 'Green', ''],
    ]
  },
  {
    name: 'High Flow TPU95 Filament',
    material: 'TPU',
    url: 'https://eu.snapmaker.com/products/black-high-flow-tpu95-filament-1-kg',
    variants: [
      ['40701280256139', 'Black', ''],
    ]
  },
  {
    name: 'Matte PLA Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/matte-pla-filament',
    variants: [
      ['45009660117131', 'Ivory White', '#FFFFFF'],
      ['45009660084363', 'Carbon Black', '#000000'],
      ['45009660248203', 'Lava Orange', '#F78E0E'],
      ['45009660346507', 'Celestial Blue', '#8BD5EE'],
      ['45009660379275', 'Sakura Pink', '#F3D6E5'],
      ['45009660149899', 'Ash Grey', '#485155'],
      ['46217794814091', 'Watermelon Red', '#FC6371'],
      ['46217794846859', 'Marine Blue', '#0078BF'],
      ['46217794879627', 'Latte Brown', '#D3B7A7'],
      ['46217794912395', 'Butter Cream', '#FEE5A5'],
      ['46217794945163', 'Violet Purple', '#6600CC'],
      ['47961085608075', 'Lavender Purple', '#AE96D4'],
      ['47961085640843', 'Mocha Brown', '#775C50'],
      ['47961085673611', 'Lime Green', '#D4E458'],
      ['47961085706379', 'Olive Green', '#68724D'],
      ['47961085739147', 'Steel Blue', '#2E4462'],
      ['47961085771915', 'Sky Blue', '#56B7E6'],
      ['47961085804683', 'Terracotta Red', '#D84B2E'],
      ['47961085837451', 'Periwinkle', '#ADB4E6'],
      ['45009660182667', 'Sunburst Yellow', '#F0BE02'],
      ['45009660280971', 'Pine Green', '#519F61'],
      ['45009660313739', 'Engine Red', '#DE1619'],
      ['45009660215435', 'Moss Mist', '#BEC9A5'],
    ]
  },
  {
    name: 'Matte PLA Filament (without RFID)',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/matte-pla-filament-without-rfid-1kg',
    variants: [
      ['46061484048523', 'Engine Red', '#DE1619'],
      ['46061483982987', 'Lava Orange', '#F78E0E'],
      ['46061484015755', 'Pine Green', '#519F61'],
      ['46061484081291', 'Celestial Blue', '#8BD5EE'],
      ['46061483950219', 'Ivory White', '#FFFFFF'],
      ['46061484179595', 'Ash Grey', '#485155'],
      ['46061484114059', 'Sakura Pink', '#F3D6E5'],
      ['46061484146827', 'Carbon Black', '#000000'],
      ['46061484212363', 'Sunburst Yellow', '#F0BE02'],
      ['46061484245131', 'Moss Mist', '#BEC9A5'],
    ]
  },
  {
    name: 'Nylon Filament',
    material: 'PA',
    url: 'https://eu.snapmaker.com/products/black-nylon-filament-1kg',
    variants: [
      ['40701280190603', 'Black', ''],
    ]
  },
  {
    name: 'PETG-CF Filament',
    material: 'PETG',
    url: 'https://eu.snapmaker.com/products/petg-cf-filament-1kg',
    variants: [
      ['49323332599947', 'Black', '#0D0D0D'],
      ['49323332763787', 'Purple', '#706399'],
      ['49323332927627', 'Burnt Orange', '#C7653E'],
      ['49323333091467', 'Dark Red', '#853E3E'],
      ['49323333255307', 'Teal', '#237D7C'],
      ['49323333419147', 'Deep Blue', '#2F4E93'],
      ['49323333582987', 'Dark Gray', '#606068'],
    ]
  },
  {
    name: 'PETG Filament',
    material: 'PETG',
    url: 'https://eu.snapmaker.com/products/petg-filament-1kg',
    variants: [
      ['34074521895051', 'Blue', '#0066FF'],
      ['34074521927819', 'Red', '#E60000'],
    ]
  },
  {
    name: 'PETG-HF Filament',
    material: 'PETG',
    url: 'https://eu.snapmaker.com/products/petg-hf-filament',
    variants: [
      ['46883432661131', 'Violet', '#493AB2'],
      ['46883431514251', 'Black', '#16171B'],
      ['46883431678091', 'White', '#F4F9FF'],
      ['46883431841931', 'Light Gray', '#ACB8C5'],
      ['46883432005771', 'Red', '#FF1523'],
      ['46883432169611', 'Orange', '#FB7E1B'],
      ['46883432333451', 'Cobalt Blue', '#0049B8'],
      ['46883432497291', 'Silver Gray', '#7C818E'],
      ['46883432824971', 'Deep Purple', '#473378'],
      ['46883432988811', 'Cocoa Brown', '#6B504C'],
      ['49134211530891', 'Yellow', '#FBE95C'],
      ['49134211563659', 'Green', '#38B837'],
      ['49134211596427', 'Dark Green', '#223622'],
      ['49134211629195', 'Light Pink', '#F5BEE9'],
    ]
  },
  {
    name: 'PETG Translucent Filament',
    material: 'PETG',
    url: 'https://eu.snapmaker.com/products/petg-translucent-filament-1kg',
    variants: [
      ['48658032427147', 'Translucent Teal', '#3DD1CE'],
      ['48658032590987', 'Translucent Blue', '#338CC4'],
      ['48658032754827', 'Translucent Gray', '#7F8896'],
      ['48658032918667', 'Translucent Green', '#537A37'],
      ['48658033082507', 'Translucent Brown', '#92713F'],
      ['48658033246347', 'Translucent Orange', '#FB8D02'],
      ['48658033410187', 'Translucent Pink', '#E68FBD'],
      ['48658033574027', 'Translucent Purple', '#D480EF'],
      ['49448362639499', 'Translucent White', '#EBEBEB'],
    ]
  },
  {
    name: 'PLA-CF Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/pla-cf-filament-1kg',
    variants: [
      ['48979615940747', 'Wine Red', '#823F2E'],
      ['48979616104587', 'Matcha Green', '#6F8653'],
      ['48979616268427', 'Graphite Gray', '#54555B'],
      ['48979616432267', 'Violet Purple', '#725E7C'],
      ['48979616596107', 'Chestnut Brown', '#9B7C56'],
      ['48979616759947', 'Denim Blue', '#49799D'],
      ['48979616923787', 'Black', '#000000'],
    ]
  },
  {
    name: 'PLA Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/pla-filament-1kg',
    variants: [
      ['34072765235339', 'Black', '#000000'],
      ['34072765268107', 'White', '#FFFFFF'],
    ]
  },
  {
    name: 'PLA Translucent Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/pla-translucent-filament-1kg',
    variants: [
      ['49323333746827', 'Translucent Amber', '#C08559'],
      ['49323333910667', 'Translucent Yellow', '#FFF200'],
      ['49323334074507', 'Translucent Green', '#008729'],
      ['49323334238347', 'Translucent Cyan', '#7FEBE2'],
      ['49323334402187', 'Translucent Light Gray', '#B1ACA6'],
      ['49323334566027', 'Translucent Light Purple', '#A7A8D9'],
      ['49323334729867', 'Translucent Blue', '#46BAE0'],
      ['49323334893707', 'Translucent Pink', '#EEBCC8'],
      ['49323335057547', 'Translucent Magenta', '#DC0080'],
      ['49323335221387', 'Translucent Dark Red', '#990002'],
    ]
  },
  {
    name: 'PVA Filament',
    material: 'PVA',
    url: 'https://eu.snapmaker.com/products/pva-filament-500g',
    variants: [
      ['40701280157835', 'Natural', ''],
    ]
  },
  {
    name: 'Silk Dual Color PLA Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/silk-dual-color-pla-filament',
    variants: [
      ['47115401756811', 'Sunset Ember', '#D9A63A', '#CC434F'],
      ['47115401920651', 'Aurora Gold', '#D9A63A', '#9675CD'],
      ['47115402084491', 'Solar Alloy', '#D9A63A', '#C4C7D9'],
      ['47115402248331', 'Mint Lemonade', '#ECED17', '#44ADE5'],
      ['47115402412171', 'Sea Glass', '#44ADE5', '#18CCAF'],
      ['47115402576011', 'Ice Lake', '#C4C7D9', '#44ADE5'],
      ['47115402739851', 'City Billboard', '#CBF914', '#D623AA'],
    ]
  },
  {
    name: 'Silk PLA Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/silk-pla-filament',
    variants: [
      ['49148386672779', 'Pearl White', '#DFE4E4'],
      ['46883430531211', 'Gold', '#F6CE1B'],
      ['46883430695051', 'Silver', '#BCC2C8'],
      ['46883430858891', 'Copper', '#AF6B4C'],
      ['46883431022731', 'Garnet Red', '#C1443F'],
      ['46883431186571', 'Pearl Pink', '#EFC2CA'],
      ['46883431350411', 'Sapphire Blue', '#768EC7'],
      ['49148386574475', 'Neon Green', '#A8FF54'],
      ['49148386607243', 'Aqua Blue', '#4CC1CB'],
      ['49148386640011', 'Emerald Green', '#55B687'],
      ['49448424341643', 'Ink Black', '#363538'],
      ['49448424374411', 'Bright Orange', '#EB6232'],
      ['49448424407179', 'Olive Green', '#7F865B'],
      ['49448424439947', 'Champagne', '#F3CFB2'],
    ]
  },
  {
    name: 'Support for PLA Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/support-for-pla-filament-500g',
    variants: [
      ['51009627816075', 'Natural White', '#EBF7FF'],
    ]
  },
  {
    name: 'TPU 90A Filament',
    material: 'TPU',
    url: 'https://eu.snapmaker.com/products/tpu-90a-filament-1kg',
    variants: [
      ['47612911943819', 'Black', '#16161A'],
      ['47612912271499', 'Gray', '#B2B4B2'],
      ['47612912107659', 'White', '#F8F8F5'],
    ]
  },
  {
    name: 'TPU 95A HF Filament',
    material: 'TPU',
    url: 'https://eu.snapmaker.com/products/tpu-95a-hf-filament',
    variants: [
      ['46883433218187', 'Black', '#000000'],
      ['46883433382027', 'White', '#FFFFFF'],
      ['46883433545867', 'Silver Gray', '#9E9E9E'],
      ['46883433709707', 'Brown', '#865B41'],
      ['46883433873547', 'Bright Blue', '#0683EF'],
      ['46883434037387', 'Red', '#EE2A20'],
      ['46883434201227', 'Dark Gray', '#595E69'],
      ['46883434365067', 'Yellow', '#FFC72C'],
      ['46883434528907', 'Green', '#33A15A'],
    ]
  },
  {
    name: 'TPU Filament',
    material: 'TPU',
    url: 'https://eu.snapmaker.com/products/tpu-filament-1kg',
    variants: [
      ['40540420374667', 'Yellow', '#F5CE00'],
      ['40540420341899', 'Black', '#000000'],
    ]
  },
  {
    name: 'Wood PLA Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/wood-pla-filament-1kg',
    variants: [
      ['47909088559243', 'Oak', '#C0A086'],
      ['47909088723083', 'Maple', '#F2C6A2'],
      ['47909088886923', 'Walnut', '#775C50'],
      ['47909089050763', 'Rosewood', '#AE7575'],
    ]
  },
  {
    name: 'Wood PLA Filament (750 g)',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/wood-pla-filament-750g',
    variants: [
      ['40739670098059', 'Natural Wood', ''],
    ]
  },
  {
    name: 'PLA Full Spectrum Filament (Gray Edition)',
    fullSpectrum: true,
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/pla-full-spectrum-filament-bundle-4kg',
    variants: [
      ['49283699966091-cyan', 'Semi-Translucent Cyan', '#08ABFB'],
      ['49283699966091-magenta', 'Semi-Translucent Magenta', '#D93B90'],
      ['49283699966091-yellow', 'Semi-Translucent Yellow', '#F9ED3D'],
      ['49283699966091-gray', 'Semi-Translucent Gray', '#9199A4'],
    ]
  },
  {
    name: 'PLA Full Spectrum Filament (White Edition)',
    fullSpectrum: true,
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/pla-full-spectrum-filament-bundle-white-edition-4kg',
    variants: [
      ['50643421692043-cyan', 'Semi-Translucent Cyan', '#00C3FF'],
      ['50643421692043-magenta', 'Semi-Translucent Magenta', '#F54399'],
      ['50643421692043-yellow', 'Semi-Translucent Yellow', '#FAE727'],
      ['50643421692043-white', 'Semi-Translucent White', '#F5F4F2'],
    ]
  },
  {
    name: 'SnapSpeed CMYK Lithophane Filament',
    material: 'PLA',
    url: 'https://eu.snapmaker.com/products/snapspeed-pla-cmyk-lithophane-filament-bundle-4kg',
    variants: [
      ['50567817199755-cyan', 'Cyan', '#0086D6'],
      ['50567817199755-magenta', 'Vivid Magenta', '#EC008C'],
      ['50567817199755-yellow', 'Lemon Yellow', '#FCE300'],
      ['50567817199755-white', 'Pure White', '#FFFFFF'],
    ]
  },
]

export const snapSpeedPalette = snapmakerCatalog.find(family => family.url === snapSpeedUrl)!
  .variants.map(([id, name, hex]) => ({ id, name, hex }))
