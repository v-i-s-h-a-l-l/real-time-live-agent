"use client";

import { useSyncExternalStore } from "react";

function greetingForHour(hour: number): string {
  if (hour < 12) return "Good morning.";
  if (hour < 17) return "Good afternoon.";
  return "Good evening.";
}

function subscribe() {
  return () => {};
}

function getGreeting() {
  return greetingForHour(new Date().getHours());
}

export function WelcomeGreeting() {
  return useSyncExternalStore(subscribe, getGreeting, () => "Good afternoon.");
}
