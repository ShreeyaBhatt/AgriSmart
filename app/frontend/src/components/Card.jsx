// Shared surface. Styling lives in Tailwind utilities, not CSS.
export default function Card({ as: Tag = "section", className = "", children, ...rest }) {
  return (
    <Tag
      className={
        "rounded-2xl border border-line bg-surface shadow-[0_1px_2px_rgba(16,36,24,0.05),0_14px_32px_-18px_rgba(16,36,24,0.22)] " +
        className
      }
      {...rest}
    >
      {children}
    </Tag>
  );
}
