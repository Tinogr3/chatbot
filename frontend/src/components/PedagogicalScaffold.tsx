"use client";

export type PedagogicalScaffoldProps = {
  scaffoldMessage: string;
};

export default function PedagogicalScaffold({ scaffoldMessage }: PedagogicalScaffoldProps) {
  return (
    <div className="shrink-0 mx-4 mt-3 p-3 rounded-lg bg-emerald-50 border border-emerald-100">
      <p className="text-xs font-semibold text-emerald-800 uppercase tracking-wider mb-2">
        Andamiaje Pedagógico
      </p>
      <div className="h-2 rounded-full bg-emerald-200 overflow-hidden mb-1.5">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
          style={{ width: "65%" }}
        />
      </div>
      <p className="text-xs text-gray-600">{scaffoldMessage}</p>
    </div>
  );
}

