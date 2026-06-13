export const dynamic = "force-static";

export default function HomePage() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        fontFamily: "var(--font-primary, Inter, sans-serif)",
        gap: "16px",
        color: "var(--text-primary, #0d0d0d)",
      }}
    >
      <h1
        style={{
          fontSize: "24px",
          fontWeight: 700,
          background: "linear-gradient(135deg, #0a7cff, #1dd6c1)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
        }}
      >
        aineron.ru
      </h1>
      <p style={{ color: "var(--text-secondary, rgba(13,13,13,0.58))" }}>
        Фронтенд обновляется. Переходите по привычным ссылкам.
      </p>
      <nav style={{ display: "flex", gap: "12px" }}>
        <a
          href="/aitext/catalog/"
          style={{
            padding: "8px 16px",
            background: "#0a7cff",
            color: "#fff",
            borderRadius: "8px",
            fontSize: "14px",
            fontWeight: 500,
          }}
        >
          Каталог нейросетей
        </a>
        <a
          href="/users/pages/profile/"
          style={{
            padding: "8px 16px",
            background: "rgba(13,13,13,0.06)",
            color: "#0d0d0d",
            borderRadius: "8px",
            fontSize: "14px",
            fontWeight: 500,
          }}
        >
          Личный кабинет
        </a>
      </nav>
    </main>
  );
}
