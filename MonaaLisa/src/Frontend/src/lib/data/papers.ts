export interface Paper {
  id: string;
  title: string;
  authors: string[];
  year: number;
  abstract?: string;
}

// Dummy-Daten: anpassen/erweitern nach Bedarf
export const papers: Paper[] = [
  {
    id: 'paper-1',
    title: 'Ein Beispielpapier zu Graphen',
    authors: ['A. Autor', 'B. Beispiel'],
    year: 2023,
    abstract: 'Kurzbeschreibung des Beispielpapiers.'
  },
  {
    id: 'paper-2',
    title: 'Weiteres Beispielpapier',
    authors: ['C. Demo'],
    year: 2022
  }
];

