/** Copy the supplied value, keeping legacy selection inside the active dialog. */
export async function copyU1Text (value:string, container:HTMLElement):Promise<void> {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try { await navigator.clipboard.writeText(value); return } catch { /* HTTP/denied clipboard: use scoped selection. */ }
  }
  const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
  const selection = document.getSelection()
  const ranges = selection ? Array.from({length:selection.rangeCount},(_,i)=>selection.getRangeAt(i).cloneRange()) : []
  const input = document.createElement('textarea')
  input.value = value; input.readOnly = true; input.tabIndex = -1
  Object.assign(input.style,{position:'fixed',opacity:'0',width:'1px',height:'1px',fontSize:'16px'})
  // Appending to body loses focus to Vuetify's dialog focus trap. Append to
  // the caller's component so execCommand copies this text, never a password mask.
  container.appendChild(input)
  let suppliedText = false
  const onCopy = (event:ClipboardEvent) => {
    if (event.clipboardData) { event.clipboardData.setData('text/plain',value); event.preventDefault(); suppliedText = true }
  }
  document.addEventListener('copy',onCopy,true)
  try {
    input.focus({preventScroll:true}); input.select(); input.setSelectionRange(0,value.length)
    if (document.activeElement !== input || !document.execCommand('copy') || !suppliedText) throw new Error('copy_failed')
    // Let the browser commit the clipboard before removing the selected node.
    await new Promise<void>(resolve => setTimeout(resolve,0))
  } finally {
    document.removeEventListener('copy',onCopy,true)
    input.remove(); previous?.focus({preventScroll:true})
    if (selection) { selection.removeAllRanges(); for (const range of ranges) selection.addRange(range) }
  }
}
