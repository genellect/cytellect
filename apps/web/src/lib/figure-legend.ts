/** Only the saved draft's title has Markdown formatting. Statistical stars are literal text. */
export function plainFigureLegend(text: string): string {
  return text.trim().replace(/^\*\*([^\r\n]+)\*\*(?=\r?\n|$)/, "$1");
}
