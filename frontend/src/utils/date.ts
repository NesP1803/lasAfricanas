export const getLocalDateInputValue = (date = new Date()): string => {
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().split('T')[0];
};
