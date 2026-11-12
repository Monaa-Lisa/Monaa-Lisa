import { arxivId, searchWords } from './search-text';

describe('searchWords', () => {
  it('splits a text into lower case words', () => {
    expect(searchWords('Vaswani  Attention')).toEqual(['vaswani', 'attention']);
  });

  it('drops short words when there are longer ones', () => {
    expect(searchWords('Attention Is All You Need')).toEqual([
      'attention',
      'all',
      'you',
      'need',
    ]);
  });

  it('keeps a short word that stands alone', () => {
    expect(searchWords('AI')).toEqual(['ai']);
  });

  it('uses every word once and at most eight of them', () => {
    expect(searchWords('graph graph neural')).toEqual(['graph', 'neural']);
    expect(
      searchWords('one two three four five six seven eight nine ten'),
    ).toHaveLength(8);
  });
});

describe('arxivId', () => {
  it('reads new and old style ids', () => {
    expect(arxivId('1706.03762')).toBe('1706.03762');
    expect(arxivId(' 0711.0189 ')).toBe('0711.0189');
    expect(arxivId('hep-th/9711200')).toBe('hep-th/9711200');
    expect(arxivId('math.CO/0601001')).toBe('math.CO/0601001');
  });

  it('drops prefix, version and link', () => {
    expect(arxivId('arXiv:1706.03762v5')).toBe('1706.03762');
    expect(arxivId('https://arxiv.org/abs/1706.03762')).toBe('1706.03762');
    expect(arxivId('https://arxiv.org/pdf/1706.03762v2.pdf')).toBe(
      '1706.03762',
    );
  });

  it('is null for ordinary text', () => {
    expect(arxivId('attention is all you need')).toBeNull();
    expect(arxivId('2017')).toBeNull();
    expect(arxivId('the 1706.03762 paper')).toBeNull();
  });
});
