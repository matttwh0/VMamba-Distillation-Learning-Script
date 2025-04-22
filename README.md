# VMamba-Distillation-Learning-Script
Application of Distillation Learning method on VMamba model (small and tiny variant). 

Heavily scaled down a lot of parameters such as batch size, image size, and epochs so that this model could run in google colab with limited memory, but heavily impacted accuracy. Vmamba small and tiny also were used for this purpose. Vmamba small served as the teacher model and Vmamba tiny was the student model. 

"DeepSeek has used distillation learning techniques in developing its AI models, particularly DeepSeek R1. Distillation is a process where a large, pre-trained model (the "teacher") transfers its knowledge to a smaller, more efficient model (the "student"). DeepSeek has used this approach to create smaller, cheaper, and faster AI models that still perform comparably to larger, more complex models. "

Accuracy on super limited resources:
<img width="504" alt="Screenshot 2025-04-22 at 2 23 33 PM" src="https://github.com/user-attachments/assets/08aaad7a-9f87-4db7-8c1a-c4eb37c9e69b" />
