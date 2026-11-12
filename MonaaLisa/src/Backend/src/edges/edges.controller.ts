import {
  BadRequestException,
  Controller,
  DefaultValuePipe,
  Get,
  Param,
  ParseIntPipe,
  Query,
} from '@nestjs/common';
import {
  DEFAULT_CONNECTED,
  DEFAULT_NEIGHBOURS,
  EdgesService,
} from './edges.service';

/**
 * The citation neighbourhood of a paper. Both routes return
 * { total, items }: `items` are the most cited papers (at most `take`),
 * `total` is how many there are in the database.
 */
@Controller()
export class EdgesController {
  constructor(private readonly edges: EdgesService) {}

  /** GET /paper-citations/paper/:entryId  papers citing this paper */
  @Get('paper-citations/paper/:entryId')
  citations(
    @Param('entryId') entryId: string,
    @Query('take', new DefaultValuePipe(DEFAULT_NEIGHBOURS), ParseIntPipe)
    take: number,
  ) {
    return this.edges.citationsOf(entryId, take);
  }

  /**
   * GET /papers/:entryId/connected?by=references|citations
   * Papers citing the same papers (by=references, the default) or cited
   * together with this one (by=citations): { by, items }, each item with
   * `shared` and `score`, see the service.
   */
  @Get('papers/:entryId/connected')
  connected(
    @Param('entryId') entryId: string,
    @Query('by') by: string | undefined,
    @Query('take', new DefaultValuePipe(DEFAULT_CONNECTED), ParseIntPipe)
    take: number,
  ) {
    if (by !== undefined && by !== 'references' && by !== 'citations') {
      throw new BadRequestException('by must be "references" or "citations"');
    }
    return this.edges.connectedTo(entryId, by ?? 'references', take);
  }

  /** GET /paper-references/paper/:entryId  papers this paper cites */
  @Get('paper-references/paper/:entryId')
  references(
    @Param('entryId') entryId: string,
    @Query('take', new DefaultValuePipe(DEFAULT_NEIGHBOURS), ParseIntPipe)
    take: number,
  ) {
    return this.edges.referencesOf(entryId, take);
  }
}
