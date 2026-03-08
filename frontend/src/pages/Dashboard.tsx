import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
  ScatterChart, Scatter, CartesianGrid,
} from "recharts";
import { Activity, Clock, CheckCircle2, XCircle, TrendingUp, Zap } from "lucide-react";
import { fetchDashboardMetrics, DashboardMetrics } from "@/lib/api";

const COLORS = {
  success: "hsl(142, 72%, 50%)",
  timeout: "hsl(45, 90%, 55%)",
  not_found: "hsl(0, 62%, 50%)",
};

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: "hsl(142, 72%, 50%)",
  medium: "hsl(198, 90%, 50%)",
  hard: "hsl(45, 90%, 55%)",
  very_hard: "hsl(0, 62%, 50%)",
};

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "Лёгкие",
  medium: "Средние",
  hard: "Сложные",
  very_hard: "Очень сложные",
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs font-mono shadow-lg">
      {label && <p className="text-muted-foreground mb-1">{label}</p>}
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color || p.fill }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(2) : p.value}
        </p>
      ))}
    </div>
  );
};

const Dashboard = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);

  useEffect(() => {
    fetchDashboardMetrics().then(setMetrics);
  }, []);

  if (!metrics) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const statusData = Object.entries(metrics.status_counts).map(([name, value]) => ({
    name: name === "success" ? "Успех" : name === "timeout" ? "Таймаут" : "Не найден",
    value,
    fill: COLORS[name as keyof typeof COLORS] || COLORS.not_found,
  }));

  const diffData = Object.entries(metrics.difficulty_stats).map(([key, val]) => ({
    name: DIFFICULTY_LABELS[key] || key,
    success_rate: val.success_rate,
    avg_time: val.avg_time,
    total: val.total,
    fill: DIFFICULTY_COLORS[key] || "hsl(0, 0%, 50%)",
  }));

  const scatterData = metrics.results.map((r) => ({
    x: r.elapsed_sec,
    y: r.path_len,
    name: `${r.start} → ${r.end}`,
    status: r.status,
    fill: COLORS[r.status as keyof typeof COLORS] || COLORS.not_found,
  }));

  const statCards = [
    { label: "Всего тестов", value: metrics.total_cases, icon: Activity },
    { label: "Успешность", value: `${metrics.success_rate.toFixed(0)}%`, icon: CheckCircle2 },
    { label: "Среднее время", value: `${metrics.avg_time.toFixed(1)}с`, icon: Clock },
    { label: "Медиана", value: `${metrics.median_time.toFixed(2)}с`, icon: TrendingUp },
    { label: "P90", value: `${metrics.p90_time.toFixed(1)}с`, icon: Zap },
    { label: "Макс. время", value: `${metrics.max_time.toFixed(1)}с`, icon: XCircle },
  ];

  return (
    <div className="min-h-screen bg-background">
      <div className="absolute inset-0 bg-dot pointer-events-none opacity-20" />
      <div className="relative z-10 max-w-6xl mx-auto px-4 py-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-12"
        >
          <h1 className="text-4xl font-bold tracking-tight mb-2">
            Bench<span className="text-gradient-primary">marks</span>
          </h1>
          <p className="text-muted-foreground font-mono text-sm">
            Обновлено: {new Date(metrics.generated_at).toLocaleDateString("ru-RU")}
          </p>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-12">
          {statCards.map((card, i) => (
            <motion.div
              key={card.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="rounded-xl border border-border bg-card/60 backdrop-blur-sm p-4"
            >
              <card.icon className="w-4 h-4 text-muted-foreground mb-2" />
              <p className="text-2xl font-bold font-mono text-foreground">{card.value}</p>
              <p className="text-xs text-muted-foreground mt-1">{card.label}</p>
            </motion.div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="rounded-xl border border-border bg-card/60 backdrop-blur-sm p-6"
          >
            <h3 className="text-sm font-mono text-muted-foreground mb-6 uppercase tracking-wider">Распределение статусов</h3>
            <div className="pointer-events-none md:pointer-events-auto" style={{ touchAction: "pan-y" }}>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    dataKey="value"
                    stroke="none"
                  >
                    {statusData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-6 mt-4">
              {statusData.map((s) => (
                <div key={s.name} className="flex items-center gap-2 text-xs">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: s.fill }} />
                  <span className="text-muted-foreground">{s.name}: {s.value}</span>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="rounded-xl border border-border bg-card/60 backdrop-blur-sm p-6"
          >
            <h3 className="text-sm font-mono text-muted-foreground mb-6 uppercase tracking-wider">Успешность по сложности</h3>
            <div className="pointer-events-none md:pointer-events-auto" style={{ touchAction: "pan-y" }}>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={diffData} barSize={32}>
                  <XAxis dataKey="name" tick={{ fill: "hsl(0,0%,55%)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis hide domain={[0, 100]} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="success_rate" name="Успешность %" radius={[6, 6, 0, 0]}>
                    {diffData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} fillOpacity={0.8} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="rounded-xl border border-border bg-card/60 backdrop-blur-sm p-6"
          >
            <h3 className="text-sm font-mono text-muted-foreground mb-6 uppercase tracking-wider">Среднее время по сложности</h3>
            <div className="pointer-events-none md:pointer-events-auto" style={{ touchAction: "pan-y" }}>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={diffData} barSize={32}>
                  <XAxis dataKey="name" tick={{ fill: "hsl(0,0%,55%)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis hide />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="avg_time" name="Ср. время (с)" radius={[6, 6, 0, 0]}>
                    {diffData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} fillOpacity={0.6} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="rounded-xl border border-border bg-card/60 backdrop-blur-sm p-6"
          >
            <h3 className="text-sm font-mono text-muted-foreground mb-6 uppercase tracking-wider">Время vs Длина пути</h3>
            <div className="pointer-events-none md:pointer-events-auto" style={{ touchAction: "pan-y" }}>
              <ResponsiveContainer width="100%" height={240}>
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(0,0%,14%)" />
                  <XAxis type="number" dataKey="x" name="Время (с)" tick={{ fill: "hsl(0,0%,55%)", fontSize: 11 }} axisLine={false} />
                  <YAxis type="number" dataKey="y" name="Длина пути" tick={{ fill: "hsl(0,0%,55%)", fontSize: 11 }} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Scatter data={scatterData.filter(d => d.y > 0)} name="Результаты">
                    {scatterData.filter(d => d.y > 0).map((entry, i) => (
                      <Cell key={i} fill={entry.fill} fillOpacity={0.8} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="mt-8 rounded-xl border border-border bg-card/60 backdrop-blur-sm overflow-hidden"
        >
          <h3 className="text-sm font-mono text-muted-foreground uppercase tracking-wider p-6 pb-4">Все результаты</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs font-mono text-muted-foreground uppercase">
                  <th className="px-6 py-3 text-left">ID</th>
                  <th className="px-6 py-3 text-left">Маршрут</th>
                  <th className="px-6 py-3 text-left">Сложность</th>
                  <th className="px-6 py-3 text-right">Время</th>
                  <th className="px-6 py-3 text-right">Путь</th>
                  <th className="px-6 py-3 text-center">Статус</th>
                </tr>
              </thead>
              <tbody>
                {metrics.results.map((r, i) => (
                  <motion.tr
                    key={r.case_id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.8 + i * 0.02 }}
                    className="border-b border-border/50 hover:bg-secondary/30 transition-colors"
                  >
                    <td className="px-6 py-3 font-mono text-xs text-muted-foreground">{r.case_id}</td>
                    <td className="px-6 py-3 text-foreground">
                      <span className="text-muted-foreground">{r.start}</span>
                      <span className="text-primary mx-2">→</span>
                      <span className="text-muted-foreground">{r.end}</span>
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className="inline-block px-2 py-0.5 rounded text-[10px] font-mono uppercase"
                        style={{
                          color: DIFFICULTY_COLORS[r.difficulty],
                          backgroundColor: `${DIFFICULTY_COLORS[r.difficulty]}15`,
                        }}
                      >
                        {r.difficulty}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-right font-mono text-xs text-muted-foreground">
                      {r.elapsed_sec.toFixed(2)}с
                    </td>
                    <td className="px-6 py-3 text-right font-mono text-xs text-muted-foreground">
                      {r.path_len || "—"}
                    </td>
                    <td className="px-6 py-3 text-center">
                      <span
                        className="inline-block w-2 h-2 rounded-full"
                        style={{ backgroundColor: COLORS[r.status as keyof typeof COLORS] || COLORS.not_found }}
                      />
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default Dashboard;
