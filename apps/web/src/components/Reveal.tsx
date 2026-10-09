/** Splits Japanese text after each 、 or 。 so its phrases can brighten one by one as they scroll in. */
export function Reveal({ text }: { text: string }) {
  return <>{text.match(/[^、。]+[、。」]*/g)?.map((phrase, index) => <span key={index}>{phrase}</span>)}</>;
}
