/**
 * DateTimePicker — a consistent date + time picker that replaces datetime-local.
 *
 * Renders a date input, hour select (1–12), minute select (00/15/30/45),
 * and AM/PM select.  Accepts and emits values as "YYYY-MM-DDTHH:MM" strings
 * so they drop in as a direct replacement for datetime-local inputs.
 */

const HOURS = Array.from({ length: 12 }, (_, i) => String(i + 1));
const MINUTES = ["00", "15", "30", "45"];

/** Parse a "YYYY-MM-DDTHH:MM" string into picker components. */
function parse(value) {
  if (!value) return { date: "", hour: "6", minute: "00", ampm: "PM" };
  const [datePart, timePart] = value.split("T");
  if (!timePart) return { date: datePart, hour: "6", minute: "00", ampm: "PM" };
  const [hhStr, mmStr] = timePart.split(":");
  const hh = parseInt(hhStr, 10);
  const mm = parseInt(mmStr, 10);
  const ampm = hh >= 12 ? "PM" : "AM";
  const hour12 = hh % 12 === 0 ? 12 : hh % 12;
  // Snap minutes to nearest 15-min slot
  const nearest = [0, 15, 30, 45].reduce((a, b) =>
    Math.abs(b - mm) < Math.abs(a - mm) ? b : a
  );
  return {
    date: datePart,
    hour: String(hour12),
    minute: String(nearest).padStart(2, "0"),
    ampm,
  };
}

/** Combine picker components back into "YYYY-MM-DDTHH:MM". */
function combine(date, hour, minute, ampm) {
  if (!date) return "";
  let hh = parseInt(hour, 10) % 12;
  if (ampm === "PM") hh += 12;
  return `${date}T${String(hh).padStart(2, "0")}:${minute}`;
}

const SELECT_CLS =
  "rounded-lg bg-gray-800 px-2 py-2 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500";

export default function DateTimePicker({ value, onChange, className = "" }) {
  const { date, hour, minute, ampm } = parse(value);

  const update = (d, h, m, ap) => onChange(combine(d, h, m, ap));

  return (
    <div className={`flex items-center gap-2 flex-wrap ${className}`}>
      <input
        type="date"
        value={date}
        onChange={(e) => update(e.target.value, hour, minute, ampm)}
        className="rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
      <select
        value={hour}
        onChange={(e) => update(date, e.target.value, minute, ampm)}
        className={SELECT_CLS}
      >
        {HOURS.map((h) => (
          <option key={h} value={h}>
            {h}
          </option>
        ))}
      </select>
      <select
        value={minute}
        onChange={(e) => update(date, hour, e.target.value, ampm)}
        className={SELECT_CLS}
      >
        {MINUTES.map((m) => (
          <option key={m} value={m}>
            :{m}
          </option>
        ))}
      </select>
      <select
        value={ampm}
        onChange={(e) => update(date, hour, minute, e.target.value)}
        className={SELECT_CLS}
      >
        <option value="AM">AM</option>
        <option value="PM">PM</option>
      </select>
    </div>
  );
}
