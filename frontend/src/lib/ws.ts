export function sensorStreamPath(elevatorId: string): string {
  return `/ws/sensors/${elevatorId}`;
}

export function createSensorStreamUrl(baseUrl: string, elevatorId: string): string {
  return `${baseUrl}${sensorStreamPath(elevatorId)}`;
}
