// Gnani Timbre v2.5 catalog: https://docs.gnani.ai/api/TTS/available-voices
export interface GnaniVoiceGroup {
  language: string
  label: string
  voices: readonly string[]
}

export const GNANI_VOICE_GROUPS: readonly GnaniVoiceGroup[] = [
  { language: 'en', label: 'English', voices: ['Kaveri', 'Trupti', 'Devika', 'Pranav', 'Shlok', 'Girish'] },
  { language: 'hi', label: 'Hindi', voices: ['Nalini', 'Bhavna', 'Yashvi', 'Urmila', 'Jwala', 'Chitra', 'Ambuja', 'Deepak', 'Roopesh', 'Vikrant', 'Hemraj', 'Jalaj', 'Omkar'] },
  { language: 'hi-en', label: 'Hinglish', voices: ['Poorvi'] },
  { language: 'ta', label: 'Tamil', voices: ['Asmita', 'Trisha', 'Brinda', 'Vedika', 'Noopur'] },
  { language: 'te', label: 'Telugu', voices: ['Suhana', 'Lehara', 'Lavanya', 'Yukti', 'Varuni'] },
  { language: 'kn', label: 'Kannada', voices: ['Saanvi', 'Kavin'] },
  { language: 'ml', label: 'Malayalam', voices: ['Reshma', 'Riyaan'] },
  { language: 'mr', label: 'Marathi', voices: ['Zahira', 'Ishaan'] },
  { language: 'bn', label: 'Bengali', voices: ['Kirra', 'Dhruva'] },
  { language: 'gu', label: 'Gujarati', voices: ['Falak', 'Veera'] },
  { language: 'pa', label: 'Punjabi', voices: ['Mehuli', 'Zayan'] },
]

export function preferredGnaniVoice(language: string): string {
  return GNANI_VOICE_GROUPS.find((group) => group.language === language)?.voices[0] ?? 'Nalini'
}
