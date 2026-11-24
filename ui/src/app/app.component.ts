import { Component, inject } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MessageModule } from 'primeng/message';
import { environment } from "../environments/environment";
import { SessionService } from './services/session.service';

@Component({
  imports: [RouterModule, MessageModule, AsyncPipe],
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {
  session = inject(SessionService);

  title = 'Geneweaver';
  version = environment.version;
}
