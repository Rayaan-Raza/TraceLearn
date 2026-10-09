export function CodeBlock({
  code,
  highlightLine,
}: {
  code: string
  highlightLine?: number
}) {
  const lines = code.replace(/\r\n/g, '\n').split('\n')

  return (
    <div className="code-block" aria-label="Code editor">
      {lines.map((line, index) => (
        <div
          key={index}
          className={`code-line${highlightLine === index ? ' highlight' : ''}`}
        >
          <span className="code-gutter">{index + 1}</span>
          <span>{line.length ? line : ' '}</span>
        </div>
      ))}
    </div>
  )
}
