import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function CodeBlock({ inline, className, children, ...props }) {
  if (inline) return <code className="inline-code" {...props}>{children}</code>;
  return <pre className="code-block"><code className={className} {...props}>{children}</code></pre>;
}

export default function MarkdownMessage({ content }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        code: CodeBlock,
        table: ({ children }) => <div className="table-scroll"><table>{children}</table></div>,
        a: ({ children, href }) => <a href={href} target="_blank" rel="noreferrer">{children}</a>,
      }}>
        {content || ''}
      </ReactMarkdown>
    </div>
  );
}
