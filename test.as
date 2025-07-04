
  .data
newline:
  .asciiz  "\n"
  .text
  .globl main
main:
  li $t1, 0
  li $t2, 103
  sub $t0,$t1,$t2
  sw $t0 0($sp)
  lw $t1 0($sp)
  li $t2, 3
  mulo $t0,$t2,$t1
  sw $t0 4($sp)
  lw $t0 4($sp)
  li $t2, 3
  mulo $t0,$t0,$t2
  sw $t0 8($sp)
  lw $t0 8($sp)
  move $a0,$t0
  li $v0, 1
  syscall
  li $v0, 4
  la $a0, newline
  syscall

  # exit
  li $v0,10
  syscall
