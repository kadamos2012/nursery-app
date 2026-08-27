import React, { useState, useEffect, useCallback } from "react";
import {
  Home, BookOpen, CalendarCheck, MessageCircle, Sun, Moon, UtensilsCrossed,
  Smile, Clock, CreditCard, Send, CheckCircle2, Settings, LogOut,
  Loader2, AlertCircle, Bell, BellOff, Megaphone, MapPin, Images
} from "lucide-react";

const C = {
  bg: "#F4F7F1", card: "#FFFFFF", ink: "#1F2A22", inkSoft: "#5B6B5E",
  primary: "#2F5D50", primarySoft: "#DCEAE3", honey: "#E7A93B", honeySoft: "#FBEBCB",
  coral: "#E1725D", coralSoft: "#F8DFD9", line: "#E4E9E1",
};
const displayFont = "'Cairo', 'Tahoma', sans-serif";
const bodyFont = "'Tajawal', 'Tahoma', sans-serif";

// The backend URL. In production this points at the deployed Flask API.
const API_BASE = import.meta.env.VITE_API_BASE || "https://nursery-app-f5of.onrender.com";

function useApi() {
  return useCallback(async (path, options = {}) => {
    const res = await fetch(API_BASE + path, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      let msg = "حصل خطأ في الاتصال بالسيرفر";
      try { msg = (await res.json()).error || msg; } catch (_) {}
      throw new Error(msg);
    }
    return res.json();
  }, []);
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

function Avatar({ size = 44, letter = "؟" }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%",
      background: `linear-gradient(135deg, ${C.honey}, ${C.primary})`,
      display: "flex", alignItems: "center", justifyContent: "center",
      color: "white", fontFamily: displayFont, fontWeight: 700, fontSize: size * 0.4, flexShrink: 0,
    }}>
      {letter}
    </div>
  );
}

function Spinner({ label }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, padding: 60 }}>
      <div className="breathe" style={{
        width: 44, height: 44, borderRadius: "50%",
        background: `linear-gradient(135deg, ${C.honey}, ${C.primary})`,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Sun size={20} color="white" />
      </div>
      <span style={{ fontFamily: bodyFont, fontSize: 13, color: C.inkSoft }}>{label}</span>
      <style>{`
        .breathe { animation: breathe 1.6s ease-in-out infinite; }
        @keyframes breathe { 0%, 100% { transform: scale(0.9); opacity: 0.85; } 50% { transform: scale(1.05); opacity: 1; } }
        @media (prefers-reduced-motion: reduce) { .breathe { animation: none; } }
      `}</style>
    </div>
  );
}

function ErrorNote({ message }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, background: C.coralSoft, color: "#B23A22",
      padding: "10px 14px", borderRadius: 12, fontFamily: bodyFont, fontSize: 12.5, margin: "0 14px 12px",
    }}>
      <AlertCircle size={15} />
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Push notifications
// ---------------------------------------------------------------------------
function useNotifications(apiFetch) {
  const [status, setStatus] = useState("unknown"); // unknown | unsupported | denied | off | on
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
      setStatus("unsupported");
      return;
    }
    if (Notification.permission === "denied") { setStatus("denied"); return; }
    navigator.serviceWorker.ready.then((reg) => reg.pushManager.getSubscription()).then((sub) => {
      setStatus(sub ? "on" : "off");
    }).catch(() => setStatus("off"));
  }, []);

  const enable = async () => {
    setBusy(true);
    try {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") { setStatus("denied"); return; }

      const { publicKey } = await apiFetch("/api/push/vapid-public-key");
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
      await apiFetch("/api/push/subscribe", { method: "POST", body: JSON.stringify(sub.toJSON()) });
      setStatus("on");
    } catch (e) {
      setStatus("off");
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    setBusy(true);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await apiFetch("/api/push/unsubscribe", { method: "POST", body: JSON.stringify({ endpoint: sub.endpoint }) });
        await sub.unsubscribe();
      }
      setStatus("off");
    } finally {
      setBusy(false);
    }
  };

  return { status, busy, enable, disable };
}

function NotificationBanner({ notifications }) {
  if (notifications.status === "on" || notifications.status === "unsupported") return null;
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
      background: C.honeySoft, borderRadius: 14, padding: "12px 14px", margin: "0 14px 14px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Bell size={16} color="#946515" />
        <span style={{ fontFamily: bodyFont, fontSize: 12.5, color: C.ink }}>
          فعّلي الإشعارات عشان توصلك تحديثات طفلك أول بأول
        </span>
      </div>
      <button
        onClick={notifications.enable}
        disabled={notifications.busy || notifications.status === "denied"}
        style={{
          background: C.primary, color: "white", border: "none", borderRadius: 10, padding: "7px 12px",
          fontFamily: bodyFont, fontSize: 11.5, fontWeight: 700, whiteSpace: "nowrap", opacity: notifications.status === "denied" ? 0.5 : 1,
        }}
      >
        {notifications.status === "denied" ? "محظورة من المتصفح" : notifications.busy ? "..." : "تفعيل"}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings sheet
// ---------------------------------------------------------------------------
function SettingsSheet({ onClose, notifications, apiFetch }) {
  const [telegram, setTelegram] = useState(null);

  useEffect(() => {
    apiFetch("/api/parent/telegram-link").then(setTelegram).catch(() => {});
  }, [apiFetch]);

  return (
    <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 20, display: "flex", alignItems: "flex-end" }}>
      <div style={{ background: "white", width: "100%", borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 20 }} dir="rtl">
        <div style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 15, color: C.ink, marginBottom: 14 }}>الإعدادات</div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: `1px solid ${C.line}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {notifications.status === "on" ? <Bell size={16} color={C.primary} /> : <BellOff size={16} color={C.inkSoft} />}
            <span style={{ fontFamily: bodyFont, fontSize: 13, color: C.ink }}>إشعارات التحديثات</span>
          </div>
          {notifications.status === "on" ? (
            <button onClick={notifications.disable} style={{ background: "none", border: `1px solid ${C.line}`, borderRadius: 10, padding: "6px 12px", fontFamily: bodyFont, fontSize: 12, color: C.inkSoft }}>
              إيقاف
            </button>
          ) : (
            <button onClick={notifications.enable} disabled={notifications.status === "denied"} style={{ background: C.primary, color: "white", border: "none", borderRadius: 10, padding: "6px 12px", fontFamily: bodyFont, fontSize: 12, fontWeight: 700, opacity: notifications.status === "denied" ? 0.5 : 1 }}>
              {notifications.status === "denied" ? "محظورة" : "تفعيل"}
            </button>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: `1px solid ${C.line}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Send size={16} color={telegram?.linked ? C.primary : C.inkSoft} />
            <span style={{ fontFamily: bodyFont, fontSize: 13, color: C.ink }}>إشعارات تليجرام</span>
          </div>
          {telegram?.linked ? (
            <span style={{ fontFamily: bodyFont, fontSize: 12, color: C.primary, fontWeight: 700 }}>متصل ✅</span>
          ) : telegram?.link ? (
            <a href={telegram.link} target="_blank" rel="noreferrer" style={{ background: C.primary, color: "white", borderRadius: 10, padding: "6px 12px", fontFamily: bodyFont, fontSize: 12, fontWeight: 700, textDecoration: "none" }}>
              ربط تليجرام
            </a>
          ) : (
            <span style={{ fontFamily: bodyFont, fontSize: 11, color: C.inkSoft }}>غير متاح حالياً</span>
          )}
        </div>

        <button onClick={onClose} style={{ width: "100%", padding: 13, background: C.primary, color: "white", border: "none", borderRadius: 12, fontFamily: bodyFont, fontWeight: 700, fontSize: 14, marginTop: 18 }}>
          تم
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Child switcher (for a parent linked to more than one child)
// ---------------------------------------------------------------------------
function ChildSwitcherSheet({ children, activeChildId, onSelect, onClose }) {
  return (
    <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 20, display: "flex", alignItems: "flex-end" }}>
      <div style={{ background: "white", width: "100%", borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 20 }} dir="rtl">
        <div style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 15, color: C.ink, marginBottom: 14 }}>أطفالي</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {children.map((c) => (
            <button
              key={c.id}
              onClick={() => { onSelect(c.id); onClose(); }}
              style={{
                display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", borderRadius: 14,
                border: c.id === activeChildId ? `2px solid ${C.primary}` : `1px solid ${C.line}`,
                background: c.id === activeChildId ? C.primarySoft : "white", textAlign: "right",
              }}
            >
              <Avatar size={38} letter={c.name?.[0] || "؟"} />
              <div>
                <div style={{ fontFamily: bodyFont, fontWeight: 700, fontSize: 13.5, color: C.ink }}>{c.name}</div>
                <div style={{ fontFamily: bodyFont, fontSize: 11.5, color: C.inkSoft, marginTop: 1 }}>{c.class_name}</div>
              </div>
            </button>
          ))}
        </div>
        <button onClick={onClose} style={{ width: "100%", padding: 13, background: "none", border: `1px solid ${C.line}`, borderRadius: 12, fontFamily: bodyFont, fontWeight: 700, fontSize: 14, marginTop: 16, color: C.inkSoft }}>
          إغلاق
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------
function LoginScreen({ apiFetch, onLoggedIn }) {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [branding, setBranding] = useState(null);

  useEffect(() => {
    apiFetch("/api/nursery/branding").then(setBranding).catch(() => {});
  }, [apiFetch]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ role: "parent", phone, password }),
      });
      onLoggedIn(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div dir="rtl" style={{ display: "flex", flexDirection: "column", justifyContent: "center", flex: 1, padding: 24, background: C.bg }}>
      <div style={{ textAlign: "center", marginBottom: 26 }}>
        {branding?.logo_url ? (
          <img src={branding.logo_url} alt={branding.name} style={{ width: 64, height: 64, borderRadius: 16, objectFit: "cover" }} />
        ) : (
          <Avatar size={56} letter="👋" />
        )}
        <div style={{ fontFamily: displayFont, fontWeight: 800, fontSize: 19, color: C.ink, marginTop: 12 }}>
          {branding?.name || "أهلاً بيكي"}
        </div>
        <div style={{ fontFamily: bodyFont, fontSize: 12.5, color: C.inkSoft, marginTop: 4 }}>سجلي دخولك لمتابعة طفلك</div>
      </div>

      {error && <ErrorNote message={error} />}

      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <input
          type="tel" placeholder="رقم الهاتف" value={phone} required
          onChange={(e) => setPhone(e.target.value)}
          style={{ padding: "13px 16px", borderRadius: 14, border: `1px solid ${C.line}`, fontFamily: bodyFont, fontSize: 14, background: "white" }}
        />
        <input
          type="password" placeholder="كلمة المرور" value={password} required
          onChange={(e) => setPassword(e.target.value)}
          style={{ padding: "13px 16px", borderRadius: 14, border: `1px solid ${C.line}`, fontFamily: bodyFont, fontSize: 14, background: "white" }}
        />
        <button type="submit" disabled={loading} style={{
          padding: 14, background: C.primary, color: "white", border: "none", borderRadius: 14,
          fontFamily: bodyFont, fontWeight: 700, fontSize: 14.5, marginTop: 6, opacity: loading ? 0.7 : 1,
        }}>
          {loading ? "جاري الدخول..." : "دخول"}
        </button>
      </form>

      {branding && (branding.facebook_url || branding.instagram_url || branding.tiktok_url) && (
        <div style={{ display: "flex", justifyContent: "center", gap: 14, marginTop: 26 }}>
          {branding.facebook_url && (
            <a href={branding.facebook_url} target="_blank" rel="noreferrer" style={{ width: 36, height: 36, borderRadius: "50%", background: C.primarySoft, display: "flex", alignItems: "center", justifyContent: "center", textDecoration: "none", fontSize: 16 }}>📘</a>
          )}
          {branding.instagram_url && (
            <a href={branding.instagram_url} target="_blank" rel="noreferrer" style={{ width: 36, height: 36, borderRadius: "50%", background: C.honeySoft, display: "flex", alignItems: "center", justifyContent: "center", textDecoration: "none", fontSize: 16 }}>📷</a>
          )}
          {branding.tiktok_url && (
            <a href={branding.tiktok_url} target="_blank" rel="noreferrer" style={{ width: 36, height: 36, borderRadius: "50%", background: C.coralSoft, display: "flex", alignItems: "center", justifyContent: "center", textDecoration: "none", fontSize: 16 }}>🎵</a>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
function DayPathCard({ today }) {
  if (!today || !today.exists) {
    return (
      <div style={{ background: C.card, borderRadius: 18, padding: 20, textAlign: "center" }}>
        <Sun size={22} color={C.honey} />
        <p style={{ fontFamily: bodyFont, fontSize: 13, color: C.inkSoft, marginTop: 8 }}>لسه معملتش المعلمة تحديث النهاردة</p>
      </div>
    );
  }
  return (
    <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 15, color: C.ink }}>تحديث النهاردة</span>
        <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: C.inkSoft, fontFamily: bodyFont }}>
          <Sun size={14} color={C.honey} /> {today.date}
        </span>
      </div>
      <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
        <div style={{ flex: 1, background: C.primarySoft, borderRadius: 14, padding: 12 }}>
          <UtensilsCrossed size={16} color={C.primary} />
          <div style={{ fontFamily: bodyFont, fontSize: 11, color: C.inkSoft, marginTop: 6 }}>الأكل</div>
          <div style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 12.5, color: C.ink, marginTop: 2 }}>{today.meal_status || "—"}</div>
        </div>
        <div style={{ flex: 1, background: C.honeySoft, borderRadius: 14, padding: 12 }}>
          <Moon size={16} color={C.honey} />
          <div style={{ fontFamily: bodyFont, fontSize: 11, color: C.inkSoft, marginTop: 6 }}>القيلولة</div>
          <div style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 12.5, color: C.ink, marginTop: 2 }}>
            {today.nap_minutes ? `${today.nap_minutes} دقيقة` : "—"}
          </div>
        </div>
        <div style={{ flex: 1, background: C.coralSoft, borderRadius: 14, padding: 12 }}>
          <Smile size={16} color={C.coral} />
          <div style={{ fontFamily: bodyFont, fontSize: 11, color: C.inkSoft, marginTop: 6 }}>المزاج</div>
          <div style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 16, marginTop: 2 }}>{today.mood || "—"}</div>
        </div>
      </div>
      {today.note && (
        <p style={{ fontFamily: bodyFont, fontSize: 13, color: C.ink, lineHeight: 1.7, margin: 0, background: C.bg, padding: 12, borderRadius: 12 }}>
          {today.note}
        </p>
      )}
    </div>
  );
}

function MedicalAlertBanner({ notes }) {
  if (!notes) return null;
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 8, background: C.coralSoft, color: "#B23A22",
      padding: "12px 14px", borderRadius: 14, fontFamily: bodyFont, fontSize: 13, fontWeight: 700,
    }}>
      <span style={{ fontSize: 16 }}>⚠️</span>
      <span>بيانات طبية مسجلة: {notes}</span>
    </div>
  );
}

function PaymentReminderBanner({ status }) {
  const partTime = status?.part_time;
  return (
    <>
      {status && !status.paid && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
          background: C.honeySoft, padding: "12px 14px", borderRadius: 14,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Clock size={16} color="#946515" />
            <span style={{ fontFamily: bodyFont, fontSize: 12.5, color: "#946515", fontWeight: 700 }}>
              مصروفات شهر {status.month}/{status.year} لسه متسددتش
            </span>
          </div>
          <span style={{ fontFamily: displayFont, fontWeight: 800, fontSize: 14, color: "#946515" }}>
            {Math.round(parseFloat(status.amount))} ج
          </span>
        </div>
      )}
      {partTime && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
          background: partTime.used >= partTime.max ? C.coralSoft : C.primarySoft, padding: "10px 14px", borderRadius: 14,
        }}>
          <span style={{ fontFamily: bodyFont, fontSize: 12, color: partTime.used >= partTime.max ? "#B23A22" : C.primary, fontWeight: 700 }}>
            أيام الدوام الجزئي هذا الشهر
          </span>
          <span style={{ fontFamily: displayFont, fontWeight: 800, fontSize: 13, color: partTime.used >= partTime.max ? "#B23A22" : C.primary }}>
            {partTime.used} / {partTime.max}
          </span>
        </div>
      )}
    </>
  );
}

function AnnouncementsCard({ announcements }) {
  if (!announcements || announcements.length === 0) return null;
  return (
    <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <Megaphone size={17} color={C.primary} />
        <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 14, color: C.ink }}>إعلانات الحضانة</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {announcements.map((a) => (
          <div key={a.id} style={{ background: C.bg, borderRadius: 12, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
              <span style={{ fontFamily: bodyFont, fontWeight: 700, fontSize: 12.5, color: C.ink }}>{a.title}</span>
              <span style={{ fontFamily: bodyFont, fontSize: 9.5, color: C.inkSoft }}>{a.scope}</span>
            </div>
            <p style={{ fontFamily: bodyFont, fontSize: 12, color: C.ink, margin: 0, lineHeight: 1.6 }}>{a.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function TripsCard({ apiFetch, childId }) {
  const [trips, setTrips] = useState([]);
  const [busy, setBusy] = useState(null);

  const load = useCallback(() => {
    apiFetch(`/api/child/${childId}/trips`).then(setTrips).catch(() => {});
  }, [childId, apiFetch]);

  useEffect(() => { load(); }, [load]);

  const subscribe = async (tripId) => {
    setBusy(tripId);
    try {
      await apiFetch(`/api/child/${childId}/trips/${tripId}/register`, { method: "POST" });
      load();
    } finally {
      setBusy(null);
    }
  };

  if (!trips || trips.length === 0) return null;

  return (
    <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <MapPin size={17} color={C.primary} />
        <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 14, color: C.ink }}>الرحلات المتاحة</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {trips.map((t) => (
          <div key={t.id} style={{ background: C.bg, borderRadius: 12, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <span style={{ fontFamily: bodyFont, fontWeight: 700, fontSize: 13, color: C.ink }}>{t.title}</span>
              <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 13, color: C.primary }}>{Math.round(parseFloat(t.price))} ج</span>
            </div>
            {t.date && <div style={{ fontFamily: bodyFont, fontSize: 11, color: C.inkSoft, marginTop: 2 }}>📅 {t.date}</div>}
            {t.description && <p style={{ fontFamily: bodyFont, fontSize: 12, color: C.ink, margin: "6px 0", lineHeight: 1.6 }}>{t.description}</p>}
            {t.registration ? (
              <div style={{ marginTop: 8, fontFamily: bodyFont, fontSize: 11.5, fontWeight: 700, color: t.registration.paid ? C.primary : "#946515" }}>
                {t.registration.paid ? "✅ الاشتراك مؤكد ومدفوع" : "⏳ تم تسجيل الاشتراك، في انتظار السداد"}
              </div>
            ) : (
              <button
                onClick={() => subscribe(t.id)}
                disabled={busy === t.id}
                className="press"
                style={{ marginTop: 8, width: "100%", padding: 10, background: C.primary, color: "white", border: "none", borderRadius: 10, fontFamily: bodyFont, fontWeight: 700, fontSize: 12.5, opacity: busy === t.id ? 0.6 : 1 }}
              >
                {busy === t.id ? "جاري الاشتراك..." : "اشتراك الآن"}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ClassPhotosCard({ apiFetch, childId }) {
  const [photos, setPhotos] = useState([]);

  useEffect(() => {
    if (!childId) return;
    apiFetch(`/api/child/${childId}/class-photos`).then(setPhotos).catch(() => {});
  }, [childId, apiFetch]);

  if (!photos || photos.length === 0) return null;

  return (
    <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <Images size={17} color={C.primary} />
        <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 14, color: C.ink }}>صور الفصل</span>
      </div>
      <div style={{ display: "flex", gap: 8, overflowX: "auto" }}>
        {photos.map((p) => (
          <div key={p.id} style={{ flexShrink: 0, width: 100 }}>
            <img src={p.url} alt={p.caption || ""} style={{ width: 100, height: 100, borderRadius: 12, objectFit: "cover" }} />
            {p.caption && <div style={{ fontFamily: bodyFont, fontSize: 10, color: C.inkSoft, marginTop: 4 }}>{p.caption}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function SpecialRequestCard({ apiFetch, childId }) {
  const [requests, setRequests] = useState([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(() => {
    apiFetch(`/api/child/${childId}/special-requests`).then(setRequests).catch(() => {});
  }, [childId, apiFetch]);

  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!text.trim()) return;
    setSending(true);
    try {
      await apiFetch(`/api/child/${childId}/special-requests`, { method: "POST", body: JSON.stringify({ text }) });
      setText("");
      setShowForm(false);
      load();
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <AlertCircle size={17} color={C.primary} />
          <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 14, color: C.ink }}>طلب خاص للمعلمة</span>
        </div>
        {!showForm && (
          <button onClick={() => setShowForm(true)} className="press" style={{ background: C.primarySoft, color: C.primary, border: "none", borderRadius: 10, padding: "6px 12px", fontFamily: bodyFont, fontSize: 11.5, fontWeight: 700 }}>
            + طلب جديد
          </button>
        )}
      </div>

      {showForm && (
        <div style={{ marginBottom: 12 }}>
          <textarea
            value={text} onChange={(e) => setText(e.target.value)} rows={3}
            placeholder="مثال: محتاج ياخد الدواء الساعة 12، أو حطيتله جاكيت النهاردة برد..."
            style={{ width: "100%", padding: 10, borderRadius: 10, border: `1px solid ${C.line}`, fontFamily: bodyFont, fontSize: 13, resize: "vertical" }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={submit} disabled={sending} className="press" style={{ flex: 1, padding: 10, background: C.primary, color: "white", border: "none", borderRadius: 10, fontFamily: bodyFont, fontWeight: 700, fontSize: 12.5, opacity: sending ? 0.6 : 1 }}>
              {sending ? "جاري الإرسال..." : "إرسال"}
            </button>
            <button onClick={() => setShowForm(false)} style={{ padding: 10, background: "none", border: `1px solid ${C.line}`, borderRadius: 10, fontFamily: bodyFont, fontSize: 12.5, color: C.inkSoft }}>
              إلغاء
            </button>
          </div>
        </div>
      )}

      {requests.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {requests.slice(0, 4).map((r) => (
            <div key={r.id} style={{ background: C.bg, borderRadius: 10, padding: 10 }}>
              <p style={{ fontFamily: bodyFont, fontSize: 12.5, color: C.ink, margin: "0 0 4px", lineHeight: 1.5 }}>{r.text}</p>
              <span style={{ fontFamily: bodyFont, fontSize: 10.5, fontWeight: 700, color: r.status === "acknowledged" ? C.primary : "#946515" }}>
                {r.status === "acknowledged" ? `✅ وصلت (${r.acknowledged_by_name || ""})` : "⏳ في انتظار الاطلاع"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MilestonesCard({ apiFetch, childId }) {
  const [milestones, setMilestones] = useState([]);

  useEffect(() => {
    if (!childId) return;
    apiFetch(`/api/child/${childId}/milestones`).then(setMilestones).catch(() => {});
  }, [childId, apiFetch]);

  if (!milestones || milestones.length === 0) return null;

  return (
    <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 17 }}>🌟</span>
        <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 14, color: C.ink }}>رحلة النمو</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {milestones.slice(0, 5).map((m) => (
          <div key={m.id} style={{ background: C.bg, borderRadius: 10, padding: 10 }}>
            <span style={{ fontFamily: bodyFont, fontSize: 10, fontWeight: 700, color: C.primary, background: C.primarySoft, padding: "2px 8px", borderRadius: 20 }}>{m.domain}</span>
            <div style={{ fontFamily: bodyFont, fontSize: 12.5, color: C.ink, fontWeight: 700, marginTop: 6 }}>{m.title}</div>
            {m.note && <div style={{ fontFamily: bodyFont, fontSize: 11.5, color: C.inkSoft, marginTop: 2 }}>{m.note}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function TasksCard({ apiFetch, childId }) {
  const [tasks, setTasks] = useState([]);

  useEffect(() => {
    if (!childId) return;
    apiFetch(`/api/child/${childId}/tasks-today`).then(setTasks).catch(() => {});
  }, [childId, apiFetch]);

  if (!tasks || tasks.length === 0) return null;

  return (
    <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <CheckCircle2 size={17} color={C.primary} />
        <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 14, color: C.ink }}>مهام النهاردة</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {tasks.map((t) => (
          <div key={t.id} style={{
            display: "flex", alignItems: "center", gap: 10, background: t.completed ? C.primarySoft : C.bg,
            borderRadius: 10, padding: "9px 12px", borderRight: t.is_personal ? `3px solid ${C.honey}` : "none",
          }}>
            <span style={{
              width: 18, height: 18, borderRadius: 5, flexShrink: 0,
              background: t.completed ? C.primary : "white", border: `2px solid ${t.completed ? C.primary : C.line}`,
              display: "flex", alignItems: "center", justifyContent: "center", color: "white", fontSize: 11,
            }}>
              {t.completed && "✓"}
            </span>
            <span style={{ fontFamily: bodyFont, fontSize: 12.5, color: C.ink, flex: 1, textDecoration: t.completed ? "line-through" : "none" }}>
              {t.title}{t.time_label && <span style={{ color: C.inkSoft, fontSize: 11 }}> ({t.time_label})</span>}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function WeeklyScheduleCard({ apiFetch, childId }) {
  const [schedule, setSchedule] = useState(null);
  const [showFullWeek, setShowFullWeek] = useState(false);

  useEffect(() => {
    if (!childId) return;
    apiFetch(`/api/child/${childId}/weekly-schedule`).then(setSchedule).catch(() => {});
  }, [childId, apiFetch]);

  if (!schedule) return null;
  const hasAnyItems = schedule.days.some((d) => d.items.length > 0);
  if (!hasAnyItems) return null;

  const todayDay = schedule.days[schedule.today_index];
  const daysToShow = showFullWeek ? schedule.days : [todayDay];

  return (
    <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <CalendarCheck size={17} color={C.primary} />
          <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 14, color: C.ink }}>جدول الأسبوع</span>
        </div>
        <button onClick={() => setShowFullWeek(!showFullWeek)} className="press" style={{ background: C.primarySoft, color: C.primary, border: "none", borderRadius: 10, padding: "5px 10px", fontFamily: bodyFont, fontSize: 11, fontWeight: 700 }}>
          {showFullWeek ? "النهاردة بس" : "كل الأسبوع"}
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {daysToShow.map((day) => (
          <div key={day.index}>
            <div style={{ fontFamily: bodyFont, fontWeight: 700, fontSize: 12, color: day.index === schedule.today_index ? C.primary : C.inkSoft, marginBottom: 6 }}>
              {day.name} {day.index === schedule.today_index && "(النهاردة)"}
            </div>
            {day.items.length === 0 ? (
              <div style={{ fontFamily: bodyFont, fontSize: 11.5, color: C.inkSoft, paddingRight: 4 }}>مفيش نشاط مسجل</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {day.items.map((item, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, background: C.bg, borderRadius: 10, padding: "8px 10px" }}>
                    {item.icon && <span style={{ fontSize: 15 }}>{item.icon}</span>}
                    <span style={{ fontFamily: bodyFont, fontSize: 12.5, color: C.ink, flex: 1 }}>{item.activity}</span>
                    {item.time_label && <span style={{ fontFamily: bodyFont, fontSize: 10.5, color: C.inkSoft }}>{item.time_label}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function HomeTab({ apiFetch, childId, notifications, medicalNotes }) {
  const [today, setToday] = useState(null);
  const [paymentStatus, setPaymentStatus] = useState(null);
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!childId) return;
    setLoading(true);
    Promise.all([
      apiFetch(`/api/child/${childId}/today`),
      apiFetch(`/api/child/${childId}/payment-status`).catch(() => null),
      apiFetch(`/api/child/${childId}/announcements`).catch(() => []),
    ]).then(([t, p, a]) => { setToday(t); setPaymentStatus(p); setAnnouncements(a || []); })
      .catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [childId, apiFetch]);

  if (loading) return <Spinner label="بنجيب تحديث النهاردة..." />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, padding: "16px 14px 90px" }}>
      <NotificationBanner notifications={notifications} />
      {error && <ErrorNote message={error} />}
      <MedicalAlertBanner notes={medicalNotes} />
      <PaymentReminderBanner status={paymentStatus} />
      <TasksCard apiFetch={apiFetch} childId={childId} />
      <MilestonesCard apiFetch={apiFetch} childId={childId} />
      <WeeklyScheduleCard apiFetch={apiFetch} childId={childId} />
      <AnnouncementsCard announcements={announcements} />
      <TripsCard apiFetch={apiFetch} childId={childId} />
      <ClassPhotosCard apiFetch={apiFetch} childId={childId} />
      <SpecialRequestCard apiFetch={apiFetch} childId={childId} />
      <DayPathCard today={today} />
    </div>
  );
}

function LogsTab({ apiFetch, childId }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!childId) return;
    setLoading(true);
    apiFetch(`/api/child/${childId}/logs?limit=30`).then(setLogs).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [childId, apiFetch]);

  if (loading) return <Spinner label="بنجيب السجل اليومي..." />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: "16px 14px 90px" }}>
      {error && <ErrorNote message={error} />}
      {logs.length === 0 && !error && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, marginTop: 50 }}>
          <BookOpen size={28} color={C.line} />
          <p style={{ fontFamily: bodyFont, fontSize: 13, color: C.inkSoft, textAlign: "center", margin: 0 }}>
            هنا هيتجمع سجل يوميات طفلك يوم بيوم
          </p>
        </div>
      )}
      {logs.map((log, i) => (
        <div key={i} style={{ background: C.card, borderRadius: 16, padding: 14, boxShadow: "0 2px 10px rgba(47,93,80,0.05)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontFamily: bodyFont, fontWeight: 700, fontSize: 13, color: C.ink }}>{log.date}</span>
            <span style={{ fontSize: 18 }}>{log.mood || "—"}</span>
          </div>
          <div style={{ display: "flex", gap: 14, marginBottom: 8 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: bodyFont, fontSize: 11.5, color: C.inkSoft }}>
              <UtensilsCrossed size={13} color={C.primary} /> {log.meal_status || "—"}
            </span>
            {log.nap_minutes && (
              <span style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: bodyFont, fontSize: 11.5, color: C.inkSoft }}>
                <Moon size={13} color={C.honey} /> نام {log.nap_minutes} دقيقة
              </span>
            )}
          </div>
          {log.note && <p style={{ fontFamily: bodyFont, fontSize: 12.5, color: C.ink, lineHeight: 1.6, margin: 0 }}>{log.note}</p>}
        </div>
      ))}
    </div>
  );
}

function AttendanceTab({ apiFetch, childId }) {
  const [attendance, setAttendance] = useState([]);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!childId) return;
    const now = new Date();
    setLoading(true);
    Promise.all([
      apiFetch(`/api/child/${childId}/attendance?year=${now.getFullYear()}&month=${now.getMonth() + 1}`),
      apiFetch(`/api/child/${childId}/payments`),
    ]).then(([a, p]) => { setAttendance(a); setPayments(p); }).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [childId, apiFetch]);

  if (loading) return <Spinner label="بنجيب الحضور والمصروفات..." />;
  const presentCount = attendance.filter((r) => r.present).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, padding: "16px 14px 90px" }}>
      {error && <ErrorNote message={error} />}
      <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <CalendarCheck size={17} color={C.primary} />
          <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 14, color: C.ink }}>الحضور هذا الشهر</span>
        </div>
        <div style={{ fontFamily: bodyFont, fontSize: 13, color: C.ink }}>{presentCount} يوم حضور من أصل {attendance.length} تم تسجيله</div>
      </div>

      <div style={{ background: C.card, borderRadius: 18, padding: 16, boxShadow: "0 2px 10px rgba(47,93,80,0.06)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <CreditCard size={17} color={C.primary} />
          <span style={{ fontFamily: displayFont, fontWeight: 700, fontSize: 14, color: C.ink }}>المصروفات</span>
        </div>
        {payments.length === 0 && <p style={{ fontFamily: bodyFont, fontSize: 12.5, color: C.inkSoft }}>لسه مفيش سجل مصروفات</p>}
        {payments.map((p, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: p.paid ? C.primarySoft : C.honeySoft, borderRadius: 12, padding: "10px 12px", marginTop: i ? 8 : 0 }}>
            <span style={{ fontFamily: bodyFont, fontSize: 12.5, color: C.ink }}>شهر {p.month}/{p.year} — {p.amount} جنيه</span>
            <span style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: bodyFont, fontSize: 12, fontWeight: 700, color: p.paid ? C.primary : "#946515" }}>
              {p.paid ? <CheckCircle2 size={14} /> : <Clock size={14} />} {p.paid ? "مدفوع" : "لسه"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MessagesTab({ apiFetch, childId }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);

  const load = useCallback(() => {
    if (!childId) return;
    apiFetch(`/api/child/${childId}/messages`).then(setMessages).catch((e) => setError(e.message));
  }, [childId, apiFetch]);

  useEffect(() => { setLoading(true); load(); setLoading(false); }, [load]);

  const send = async () => {
    if (!text.trim()) return;
    setSending(true);
    try {
      await apiFetch(`/api/child/${childId}/messages`, { method: "POST", body: JSON.stringify({ text }) });
      setText("");
      load();
    } catch (e) { setError(e.message); } finally { setSending(false); }
  };

  if (loading) return <Spinner label="بنجيب الرسائل..." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
        {error && <ErrorNote message={error} />}
        {messages.length === 0 && !error && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, marginTop: 50 }}>
            <MessageCircle size={28} color={C.line} />
            <p style={{ fontFamily: bodyFont, fontSize: 13, color: C.inkSoft, textAlign: "center", margin: 0 }}>
              ابدئي محادثة مع المعلمة من هنا
            </p>
          </div>
        )}
        {messages.map((m, i) => {
          const mine = m.sender_type === "parent";
          return (
            <div key={i} style={{ display: "flex", justifyContent: mine ? "flex-start" : "flex-end" }}>
              <div style={{
                maxWidth: "78%", background: mine ? C.primary : C.card, color: mine ? "white" : C.ink,
                borderRadius: 16, borderBottomLeftRadius: mine ? 4 : 16, borderBottomRightRadius: mine ? 16 : 4,
                padding: "9px 13px", boxShadow: "0 1px 6px rgba(47,93,80,0.06)",
              }}>
                <p style={{ fontFamily: bodyFont, fontSize: 13, lineHeight: 1.6, margin: 0 }}>{m.text}</p>
                <div style={{ fontFamily: bodyFont, fontSize: 9.5, opacity: 0.7, marginTop: 4, textAlign: "left" }}>
                  {new Date(m.timestamp).toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", gap: 8, padding: "10px 14px calc(env(safe-area-inset-bottom, 10px) + 90px)", borderTop: `1px solid ${C.line}`, background: C.bg }}>
        <input
          value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="اكتبي رسالتك..."
          style={{ flex: 1, background: C.card, borderRadius: 20, padding: "10px 16px", fontFamily: bodyFont, fontSize: 13, border: "none", color: C.ink }}
        />
        <button onClick={send} disabled={sending} className="press" style={{ width: 40, height: 40, borderRadius: "50%", background: C.primary, border: "none", display: "flex", alignItems: "center", justifyContent: "center", opacity: sending ? 0.6 : 1 }}>
          <Send size={16} color="white" />
        </button>
      </div>
    </div>
  );
}

const TABS = [
  { key: "home", label: "الرئيسية", icon: Home },
  { key: "logs", label: "اليوميات", icon: BookOpen },
  { key: "attendance", label: "الحضور", icon: CalendarCheck },
  { key: "messages", label: "رسائل", icon: MessageCircle },
];

export default function App() {
  const apiFetch = useApi();
  const notifications = useNotifications(apiFetch);

  const [showSettings, setShowSettings] = useState(false);
  const [showChildSwitcher, setShowChildSwitcher] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [user, setUser] = useState(null);
  const [children, setChildren] = useState([]);
  const [childId, setChildId] = useState(null);
  const [tab, setTab] = useState("home");

  useEffect(() => {
    apiFetch("/api/auth/me").then((d) => { if (d.authenticated) setUser(d); }).catch(() => {}).finally(() => setAuthChecked(true));
  }, [apiFetch]);

  useEffect(() => {
    if (!user) return;
    apiFetch("/api/parent/children").then((list) => {
      setChildren(list);
      if (list.length) setChildId(list[0].id);
    }).catch(() => {});
  }, [user, apiFetch]);

  const logout = async () => {
    try { await apiFetch("/api/auth/logout", { method: "POST" }); } catch (_) {}
    setUser(null); setChildren([]); setChildId(null);
  };

  const activeChild = children.find((c) => c.id === childId);

  return (
    <div dir="rtl" style={{
      fontFamily: bodyFont, background: C.bg, minHeight: "100vh", maxWidth: 480, margin: "0 auto",
      display: "flex", flexDirection: "column", position: "relative",
    }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@600;700;800&family=Tajawal:wght@400;500;700&display=swap');
        * { box-sizing: border-box; }
        .tab-fade { animation: tabFadeIn 0.28s ease both; }
        @keyframes tabFadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
        .nav-btn { transition: transform 0.15s ease; }
        .nav-btn:active { transform: scale(0.92); }
        .nav-pill { transition: background 0.2s ease, transform 0.2s ease; }
        .press:active { transform: scale(0.97); }
        @media (prefers-reduced-motion: reduce) {
          .tab-fade, .nav-btn, .nav-pill, .press { animation: none !important; transition: none !important; }
        }
      `}</style>

      {showSettings && <SettingsSheet onClose={() => setShowSettings(false)} notifications={notifications} apiFetch={apiFetch} />}
      {showChildSwitcher && (
        <ChildSwitcherSheet
          children={children}
          activeChildId={childId}
          onSelect={setChildId}
          onClose={() => setShowChildSwitcher(false)}
        />
      )}

      {!authChecked ? (
        <Spinner label="بنتأكد من تسجيل الدخول..." />
      ) : !user ? (
        <LoginScreen apiFetch={apiFetch} onLoggedIn={setUser} />
      ) : (
        <>
          <div style={{ background: C.primary, color: "white", padding: "18px 16px 22px", borderBottomLeftRadius: 22, borderBottomRightRadius: 22 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                {activeChild?.photo_url ? (
                  <img src={activeChild.photo_url} alt={activeChild.name}
                       style={{ width: 40, height: 40, borderRadius: "50%", objectFit: "cover", border: "2px solid rgba(255,255,255,0.4)" }} />
                ) : (
                  <Avatar size={40} letter={activeChild?.name?.[0] || "؟"} />
                )}
                <button
                  onClick={() => children.length > 1 && setShowChildSwitcher(true)}
                  style={{ background: "none", border: "none", textAlign: "right", padding: 0, cursor: children.length > 1 ? "pointer" : "default" }}
                >
                  <div style={{ fontFamily: bodyFont, fontSize: 12, opacity: 0.8, display: "flex", alignItems: "center", gap: 4 }}>
                    {activeChild ? activeChild.class_name : "..."}
                    {children.length > 1 && <span style={{ fontSize: 10 }}>▾</span>}
                  </div>
                  <div style={{ fontFamily: displayFont, fontWeight: 800, fontSize: 20, marginTop: 2, color: "white" }}>{activeChild ? activeChild.name : "بنجيب بيانات طفلك"}</div>
                </button>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <button onClick={() => setShowSettings(true)} style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: "50%", width: 32, height: 32, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Settings size={15} color="white" />
                </button>
                <button onClick={logout} style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: "50%", width: 32, height: 32, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <LogOut size={15} color="white" />
                </button>
              </div>
            </div>
          </div>

          <div style={{ flex: 1, overflowY: tab === "messages" ? "hidden" : "auto", display: "flex", flexDirection: "column" }}>
            {!childId ? (
              <Spinner label="بنجيب بيانات طفلك..." />
            ) : (
              <div key={tab} className="tab-fade" style={{ display: "flex", flexDirection: "column", flex: 1 }}>
                {tab === "home" && <HomeTab apiFetch={apiFetch} childId={childId} notifications={notifications} medicalNotes={activeChild?.medical_notes} />}
                {tab === "logs" && <LogsTab apiFetch={apiFetch} childId={childId} />}
                {tab === "attendance" && <AttendanceTab apiFetch={apiFetch} childId={childId} />}
                {tab === "messages" && <MessagesTab apiFetch={apiFetch} childId={childId} />}
              </div>
            )}
          </div>

          <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, maxWidth: 480, margin: "0 auto", background: C.card, borderTop: `1px solid ${C.line}`, display: "flex", padding: "8px 8px calc(env(safe-area-inset-bottom, 8px))" }}>
            {TABS.map((t) => {
              const Icon = t.icon;
              const isActive = t.key === tab;
              return (
                <button key={t.key} onClick={() => setTab(t.key)} className="nav-btn" style={{ flex: 1, background: "none", border: "none", display: "flex", justifyContent: "center", padding: "4px 2px", cursor: "pointer" }}>
                  <div className="nav-pill" style={{
                    display: "flex", flexDirection: "column", alignItems: "center", gap: 3,
                    padding: "6px 14px", borderRadius: 14,
                    background: isActive ? C.primarySoft : "transparent",
                  }}>
                    <Icon size={19} color={isActive ? C.primary : C.inkSoft} strokeWidth={isActive ? 2.4 : 1.8} />
                    <span style={{ fontFamily: bodyFont, fontSize: 10.5, color: isActive ? C.primary : C.inkSoft, fontWeight: isActive ? 700 : 400 }}>{t.label}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
