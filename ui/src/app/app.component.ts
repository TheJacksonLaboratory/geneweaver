import { Component } from '@angular/core';
import { AsyncPipe, NgIf } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MessagesModule } from 'primeng/messages';
import { environment } from "../environments/environment";
import { SessionService } from './services/session.service';

@Component({
  standalone: true,
  imports: [RouterModule, MessagesModule, AsyncPipe, NgIf],
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {
  title = 'Geneweaver';
  version = environment.version;

  constructor(public session: SessionService) {}
}
