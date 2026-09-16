"use client";

interface Props {
  label: string;
  value: number | string;
  icon?: React.ReactNode;
  trend?: string;
  trendUp?: boolean;
}

export default function KpiCard({ label, value, icon, trend, trendUp }: Props) {
  return (
    <div className="saas-panel p-5 w-full flex flex-col justify-between h-[115px]">
      <div className="flex justify-between items-start">
        <div className="text-sm font-medium text-slate-500">
          {label}
        </div>
        {icon && (
          <div className="p-2 rounded-lg bg-slate-50 text-slate-400">
            {icon}
          </div>
        )}
      </div>
      <div className="flex items-baseline gap-3 mt-1">
        <div className="text-3xl font-bold tracking-tight text-slate-900">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
        {trend && (
          <div className={`text-xs font-semibold ${trendUp ? 'text-emerald-600' : 'text-red-500'}`}>
            {trendUp ? '↑' : '↓'} {trend}
          </div>
        )}
      </div>
    </div>
  );
}
