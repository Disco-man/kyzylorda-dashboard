// Mock events JSON structure for city incidents & infrastructure
// Each event:
// {
//   id: string;
//   type: "repair" | "emergency" | "road_work";
//   coordinates: {
//     // Either a single incident point (General Incident layer):
//     lat?: number;
//     lng?: number;
//     // Or a polyline path representing a road repair / road work segment (Road Repairs layer):
//     polyline?: [number, number][];
//   };
//   street: string;
//   title: string;
//   description: string;
//   reportedBy: string;
//   status: "ongoing" | "resolved";
//   timestamp: string; // ISO string
// }

export const events = [
  {
    id: "evt-1",
    type: "emergency",
    coordinates: {
      lat: 44.8470964,
      lng: 65.5224453
    },
    street: "Улица Коркыт Ата",
    title: "Пожар в жилом доме – Центральный район",
    description:
      "Службы экстренного реагирования выехали на вызов о пожаре в жилом доме в центре Кызылорды. Движение перенаправлено.",
    reportedBy: "Служба чрезвычайных ситуаций Кызылорды",
    status: "ongoing",
    timestamp: "2026-02-12T09:15:00Z"
  },
  {
    id: "evt-2",
    type: "repair",
    coordinates: {
      lat: 44.8484893,
      lng: 65.4964369
    },
    street: "Улица Ауэзова",
    title: "Ремонт водопровода",
    description:
      "Плановые работы по ремонту водопровода. Возможно низкое давление воды в близлежащих зданиях на улице Ауэзова.",
    reportedBy: "Городские коммунальные службы Кызылорды",
    status: "ongoing",
    timestamp: "2026-02-12T08:40:00Z"
  },
  {
    id: "evt-4",
    type: "emergency",
    coordinates: {
      lat: 44.8468026,
      lng: 65.5171670
    },
    street: "Улица Айтеке би",
    title: "Небольшая автомобильная авария",
    description:
      "Зарегистрирована незначительная автомобильная авария на перекрестке улицы Айтеке би. Ожидаются небольшие задержки движения.",
    reportedBy: "Дорожная полиция Кызылорды",
    status: "resolved",
    timestamp: "2026-02-12T09:05:00Z"
  },
  {
    id: "evt-5",
    type: "repair",
    coordinates: {
      lat: 44.7820344,
      lng: 65.5339230
    },
    street: "Улица Жибек жолы",
    title: "Ремонт электросети",
    description:
      "Ведутся работы по ремонту электросети на улице Жибек жолы. Возможны кратковременные перебои в электроснабжении.",
    reportedBy: "Энергетическая сеть Кызылорды",
    status: "ongoing",
    timestamp: "2026-02-12T06:30:00Z"
  }
];

