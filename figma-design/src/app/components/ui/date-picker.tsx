"use client";

import * as React from "react";
import { format, parseISO } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";

import { Button } from "./button";
import { Calendar } from "./calendar";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { cn } from "./utils";

type DatePickerProps = {
  value: string;
  availableDates: string[];
  onChange: (next: string) => void;
  disabled?: boolean;
  className?: string;
};

function minMaxDates(values: string[]) {
  if (!values.length) return { min: undefined as Date | undefined, max: undefined as Date | undefined };
  const parsed = values
    .map((v) => {
      try {
        return parseISO(v);
      } catch {
        return null;
      }
    })
    .filter((d): d is Date => Boolean(d) && !Number.isNaN(d.getTime()));
  if (!parsed.length) return { min: undefined, max: undefined };
  const min = parsed.reduce((a, b) => (a < b ? a : b));
  const max = parsed.reduce((a, b) => (a > b ? a : b));
  return { min, max };
}

function DatePicker({ value, availableDates, onChange, disabled, className }: DatePickerProps) {
  const { min, max } = React.useMemo(() => minMaxDates(availableDates), [availableDates]);
  const availableSet = React.useMemo(() => new Set(availableDates), [availableDates]);
  const selected = React.useMemo(() => {
    if (!value) return undefined;
    try {
      const d = parseISO(value);
      return Number.isNaN(d.getTime()) ? undefined : d;
    } catch {
      return undefined;
    }
  }, [value]);
  const [month, setMonth] = React.useState<Date | undefined>(selected ?? max);

  React.useEffect(() => {
    setMonth(selected ?? max);
  }, [selected, max]);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          className={cn("h-9 min-w-[220px] justify-start text-left font-normal", className)}
        >
          <CalendarIcon className="mr-2 size-4 opacity-70" />
          {value || "选择日期"}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          month={month}
          onMonthChange={setMonth}
          selected={selected}
          onSelect={(d) => {
            if (!d) return;
            const v = format(d, "yyyy-MM-dd");
            if (!availableSet.has(v)) return;
            onChange(v);
          }}
          disabled={(d) => {
            if (min && d < min) return true;
            if (max && d > max) return true;
            return !availableSet.has(format(d, "yyyy-MM-dd"));
          }}
        />
      </PopoverContent>
    </Popover>
  );
}

export { DatePicker };

