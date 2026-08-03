export interface Crumb {
  label: string;
  onClick?: () => void;
}

export default function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <div className="breadcrumb">
      {items.map((item, i) => (
        <span key={i} className="breadcrumb-segment">
          {item.onClick ? (
            <button type="button" className="breadcrumb-link" onClick={item.onClick}>
              {item.label}
            </button>
          ) : (
            <span className="breadcrumb-current">{item.label}</span>
          )}
          {i < items.length - 1 && <span className="breadcrumb-sep">/</span>}
        </span>
      ))}
    </div>
  );
}
