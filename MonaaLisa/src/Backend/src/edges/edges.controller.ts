import { Controller, Get, Param } from '@nestjs/common';
import { EdgesService } from './edges.service';

@Controller()
export class EdgesController {
  constructor(private readonly edges: EdgesService) {}

  /** GET /paper-citations/paper/:entryId - papers that cite this paper */
  @Get('paper-citations/paper/:entryId')
  citations(@Param('entryId') entryId: string) {
    return this.edges.citationsOf(entryId);
  }

  /** GET /paper-references/paper/:entryId - papers this paper cites */
  @Get('paper-references/paper/:entryId')
  references(@Param('entryId') entryId: string) {
    return this.edges.referencesOf(entryId);
  }
}
