/** Cartesia voices the student may pick. Any voice can be used in any spoken language. */

export interface TutorVoiceOption {
  id: string;
  name: string;
  bestFor: string;
}

export const TUTOR_VOICES: readonly TutorVoiceOption[] = [
  {
    id: "95d51f79-c397-46f9-b49a-23763d3eaa2d",
    name: "Riya",
    bestFor: "Hindi",
  },
  {
    id: "96e6974d-57a9-4325-89c8-43f065f8bd95",
    name: "Akshara",
    bestFor: "Tamil",
  },
  {
    id: "4418bb06-8329-49a1-bb11-53bb64ca0547",
    name: "Shanti",
    bestFor: "Telugu",
  },
  {
    id: "098fb15d-2597-4186-8b74-25340050b6e7",
    name: "Vishal",
    bestFor: "Hindi",
  },
  {
    id: "910fb75e-1d20-4840-ac63-ac6b26a71bdc",
    name: "Dev",
    bestFor: "Hindi",
  },
] as const;

export const DEFAULT_TUTOR_VOICE_ID = TUTOR_VOICES[0].id;

export function tutorVoiceLabel(voice: TutorVoiceOption): string {
  return `${voice.name} (best for ${voice.bestFor})`;
}
