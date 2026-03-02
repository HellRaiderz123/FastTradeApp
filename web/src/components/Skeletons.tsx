import React from 'react';

export const SkeletonCard: React.FC = () => (
  <div className="bg-slate-900 rounded-lg p-6 border border-slate-800 animate-pulse">
    <div className="h-6 bg-slate-800 rounded w-1/3 mb-4"></div>
    <div className="space-y-3">
      <div className="h-4 bg-slate-800 rounded w-full"></div>
      <div className="h-4 bg-slate-800 rounded w-5/6"></div>
      <div className="h-4 bg-slate-800 rounded w-4/6"></div>
    </div>
  </div>
);

export const SkeletonTable: React.FC<{ rows?: number }> = ({ rows = 5 }) => (
  <div className="bg-slate-900 rounded-lg border border-slate-800 overflow-hidden">
    <div className="p-4 border-b border-slate-800 animate-pulse">
      <div className="h-6 bg-slate-800 rounded w-1/4"></div>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-slate-800">
          <tr>
            {[1, 2, 3, 4, 5].map((i) => (
              <th key={i} className="p-3">
                <div className="h-4 bg-slate-700 rounded animate-pulse"></div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, idx) => (
            <tr key={idx} className="border-b border-slate-800">
              {[1, 2, 3, 4, 5].map((i) => (
                <td key={i} className="p-3">
                  <div className="h-4 bg-slate-800 rounded animate-pulse"></div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

export const SkeletonChart: React.FC = () => (
  <div className="bg-slate-900 rounded-lg p-6 border border-slate-800">
    <div className="animate-pulse">
      <div className="h-6 bg-slate-800 rounded w-1/4 mb-4"></div>
      <div className="h-64 bg-slate-800 rounded"></div>
    </div>
  </div>
);

export const SkeletonList: React.FC<{ items?: number }> = ({ items = 5 }) => (
  <div className="space-y-3">
    {Array.from({ length: items }).map((_, idx) => (
      <div key={idx} className="bg-slate-900 rounded-lg p-4 border border-slate-800 animate-pulse">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-slate-800 rounded-full"></div>
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-slate-800 rounded w-1/3"></div>
            <div className="h-3 bg-slate-800 rounded w-1/2"></div>
          </div>
        </div>
      </div>
    ))}
  </div>
);

export const SkeletonGrid: React.FC<{ cols?: number; rows?: number }> = ({ 
  cols = 3, 
  rows = 2 
}) => (
  <div className={`grid grid-cols-1 md:grid-cols-${cols} gap-4`}>
    {Array.from({ length: cols * rows }).map((_, idx) => (
      <div key={idx} className="bg-slate-900 rounded-lg p-6 border border-slate-800 animate-pulse">
        <div className="space-y-3">
          <div className="h-6 bg-slate-800 rounded w-2/3"></div>
          <div className="h-4 bg-slate-800 rounded w-full"></div>
          <div className="h-4 bg-slate-800 rounded w-5/6"></div>
        </div>
      </div>
    ))}
  </div>
);

export const SkeletonStat: React.FC = () => (
  <div className="bg-slate-900 rounded-lg p-4 border border-slate-800 animate-pulse">
    <div className="h-4 bg-slate-800 rounded w-1/2 mb-2"></div>
    <div className="h-8 bg-slate-800 rounded w-3/4"></div>
  </div>
);
