export function formatDate(iso: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(new Date(iso));
}

export function formatShortDate(iso: string) {
  const date = new Date(iso);
  const sameDay =
    date.toDateString() === new Date().toDateString();
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    ...(sameDay
      ? { hour: "2-digit", minute: "2-digit", hour12: false }
      : { year: "2-digit", month: "2-digit", day: "2-digit" }),
  }).format(date);
}
